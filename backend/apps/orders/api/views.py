from __future__ import annotations

from django.db.models import Case, IntegerField, Prefetch, Q, Value, When
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer, IsOrderDesk, IsSuperAdmin, orders_scope
from apps.accounts.roles import is_super_admin
from apps.artworks.models import ArtworkImage
from apps.core import idempotency
from apps.core.models import SiteSetting

from .. import services
from ..models import Order, OrderItem, OrderStatus, PaymentRecord
from .serializers import (
    AdminOrderListSerializer,
    AdminOrderSerializer,
    CancelSerializer,
    CheckoutSerializer,
    CustomDepositSerializer,
    CustomerOrderSerializer,
    DeliveryInputSerializer,
    NotesSerializer,
    OrderReasonSerializer,
    OrderSummarySerializer,
    PaymentInputSerializer,
    PolicySerializer,
    StaffCancelSerializer,
    policy_payload,
)

IDEMPOTENCY_HEADER = OpenApiParameter(
    "Idempotency-Key", str, location=OpenApiParameter.HEADER, required=True, description="UUID per attempt"
)


def _order_qs():
    primary = ArtworkImage.objects.filter(is_primary=True).select_related("asset")
    return Order.objects.select_related("delivery", "user").prefetch_related(
        Prefetch(
            "items",
            queryset=OrderItem.objects.select_related("artwork").prefetch_related(
                Prefetch("artwork__images", queryset=primary, to_attr="primary_images")
            ),
        ),
        "history__actor",
        "payments__recorded_by",
        "payments__confirmed_by",
    )


def _customer_out(order: Order) -> dict:
    order = _order_qs().get(pk=order.pk)
    return CustomerOrderSerializer(order, context={"settings": SiteSetting.load()}).data


# --- customer ------------------------------------------------------------------------------------------
class PolicyView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="orders_policy", responses=PolicySerializer)
    def get(self, request: Request) -> Response:
        return Response(policy_payload())


class CheckoutView(APIView):
    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout"

    @extend_schema(
        operation_id="orders_checkout",
        request=CheckoutSerializer,
        responses={201: CustomerOrderSerializer},
        parameters=[IDEMPOTENCY_HEADER],
    )
    def post(self, request: Request) -> Response:
        data = CheckoutSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = request.user

        def action():
            order = services.checkout(
                user=user,
                policy_version=v["policy_version"],
                contact={
                    "contact_name": user.display_name or f"{user.first_name} {user.last_name}".strip() or user.phone,
                    "contact_phone": user.phone,
                    "contact_email": user.email or "",
                    "governorate": v["governorate"],
                    "city": v["city"].strip(),
                    "address_line": v["address_line"].strip(),
                },
                customer_notes=v["customer_notes"],
            )
            return status.HTTP_201_CREATED, _customer_out(order)

        code, body = idempotency.run_once(request, scope="checkout", action=action)
        return Response(body, status=code)


class MyOrdersView(ListAPIView):
    permission_classes = [IsCustomer]
    serializer_class = OrderSummarySerializer

    def get_queryset(self):
        # Orders awaiting the customer's action first, then newest.
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items")
            .annotate(
                rank=Case(
                    When(status=OrderStatus.PENDING_DEPOSIT, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("rank", "-created_at")
        )

    @extend_schema(operation_id="orders_mine")
    def get(self, request: Request, *args, **kwargs) -> Response:
        # Lazily expire anything overdue so the list never shows a stale countdown.
        for order in Order.objects.filter(user=request.user, status=OrderStatus.PENDING_DEPOSIT):
            services.refresh(order)
        return super().get(request, *args, **kwargs)


def _mine(request: Request, number: str) -> Order:
    order = get_object_or_404(Order, order_number=number, user=request.user)  # IDOR-safe
    return services.refresh(order)


class MyOrderDetailView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="orders_detail", responses=CustomerOrderSerializer)
    def get(self, request: Request, number: str) -> Response:
        return Response(_customer_out(_mine(request, number)))


class MyOrderCancelView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="orders_cancel", request=CancelSerializer, responses=CustomerOrderSerializer)
    def post(self, request: Request, number: str) -> Response:
        data = CancelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = services.cancel_by_customer(
            _mine(request, number), user=request.user, reason=data.validated_data["reason"]
        )
        return Response(_customer_out(order))


# --- staff ------------------------------------------------------------------------------------------------
def _staff_out(request: Request, order: Order) -> dict:
    order = _order_qs().get(pk=order.pk)
    context = {"settings": SiteSetting.load(), "is_super_admin": is_super_admin(request.user)}
    return AdminOrderSerializer(order, context=context).data


def _desk_orders(request: Request):
    qs = Order.objects.all()
    if orders_scope(request.user) == "auction":
        qs = qs.filter(source="auction")
    return qs


def _staff_order(request: Request, number: str) -> Order:
    return services.refresh(get_object_or_404(_desk_orders(request), order_number=number))


class AdminOrderListView(ListAPIView):
    permission_classes = [IsOrderDesk]
    serializer_class = AdminOrderListSerializer

    def get_queryset(self):
        p = self.request.query_params
        qs = _desk_orders(self.request).prefetch_related("items")
        state = p.get("status", "")
        if p.get("source") in ("cart", "auction"):
            qs = qs.filter(source=p["source"])
        if state == "open":
            qs = qs.exclude(status__in=[s for s in OrderStatus.values if s in services.FINAL_STATUSES])
        elif state in OrderStatus.values:
            qs = qs.filter(status=state)
        term = p.get("search", "").strip()
        if term:
            qs = qs.filter(
                Q(order_number__icontains=term)
                | Q(contact_name__icontains=term)
                | Q(contact_phone__icontains=term.lstrip("0"))
                | Q(contact_email__icontains=term)
            )
        if state == OrderStatus.PENDING_DEPOSIT:
            return qs.order_by("reservation_expires_at")  # most urgent first
        return qs.order_by("-created_at")

    @extend_schema(
        operation_id="admin_orders_list",
        parameters=[
            OpenApiParameter("status", str, enum=["open", *OrderStatus.values]),
            OpenApiParameter("source", str, enum=["cart", "auction"]),
            OpenApiParameter("search", str),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        services.expire_due_orders()  # cheap; keeps the list truthful between Beat runs
        return super().get(request, *args, **kwargs)


class AdminOrderDetailView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(operation_id="admin_order_detail", responses=AdminOrderSerializer)
    def get(self, request: Request, number: str) -> Response:
        return Response(_staff_out(request, _staff_order(request, number)))

    @extend_schema(operation_id="admin_order_notes", request=NotesSerializer, responses=AdminOrderSerializer)
    def patch(self, request: Request, number: str) -> Response:
        data = NotesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = services.update_internal_notes(
            _staff_order(request, number), actor=request.user, notes=data.validated_data["internal_notes"]
        )
        return Response(_staff_out(request, order))


class AdminPaymentsView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(
        operation_id="admin_order_payment_record",
        request=PaymentInputSerializer,
        responses={201: AdminOrderSerializer},
        parameters=[IDEMPOTENCY_HEADER],
    )
    def post(self, request: Request, number: str) -> Response:
        data = PaymentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = _staff_order(request, number)

        def action():
            services.record_payment(order, actor=request.user, **data.validated_data)
            return status.HTTP_201_CREATED, _staff_out(request, order)

        code, body = idempotency.run_once(request, scope=f"payment:{order.pk}", action=action)
        return Response(body, status=code)


def _payment(number: str, payment_id) -> PaymentRecord:
    return get_object_or_404(
        PaymentRecord.objects.select_related("order"), public_id=payment_id, order__order_number=number
    )


class AdminPaymentConfirmView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(operation_id="admin_order_payment_confirm", request=None, responses=AdminOrderSerializer)
    def post(self, request: Request, number: str, payment_id: str) -> Response:
        record = services.confirm_payment(_payment(number, payment_id), actor=request.user)
        return Response(_staff_out(request, record.order))


class AdminPaymentVoidView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(
        operation_id="admin_order_payment_void", request=OrderReasonSerializer, responses=AdminOrderSerializer
    )
    def post(self, request: Request, number: str, payment_id: str) -> Response:
        data = OrderReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.void_payment(
            _payment(number, payment_id), actor=request.user, reason=data.validated_data["reason"]
        )
        return Response(_staff_out(request, record.order))


class AdminOrderItemRemoveView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(
        operation_id="admin_order_item_remove", request=OrderReasonSerializer, responses=AdminOrderSerializer
    )
    def post(self, request: Request, number: str, item_id: str) -> Response:
        data = OrderReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = _staff_order(request, number)
        item = get_object_or_404(OrderItem, public_id=item_id, order=order)
        order = services.remove_item(order, item, actor=request.user, reason=data.validated_data["reason"])
        return Response(_staff_out(request, order))


class AdminOrderDepositView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(
        operation_id="admin_order_custom_deposit", request=CustomDepositSerializer, responses=AdminOrderSerializer
    )
    def post(self, request: Request, number: str) -> Response:
        data = CustomDepositSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        order = services.set_custom_deposit(
            _staff_order(request, number),
            actor=request.user,
            amount=data.validated_data["amount"],
            reason=data.validated_data["reason"],
        )
        return Response(_staff_out(request, order))


class AdminOrderCancelView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(operation_id="admin_order_cancel", request=StaffCancelSerializer, responses=AdminOrderSerializer)
    def post(self, request: Request, number: str) -> Response:
        data = StaffCancelSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fn = services.cancel_by_platform if data.validated_data["kind"] == "platform" else services.cancel_for_customer
        order = fn(_staff_order(request, number), actor=request.user, reason=data.validated_data["reason"])
        return Response(_staff_out(request, order))


class AdminOrderDeliveryView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(operation_id="admin_order_delivery", request=DeliveryInputSerializer, responses=AdminOrderSerializer)
    def put(self, request: Request, number: str) -> Response:
        data = DeliveryInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        order = _staff_order(request, number)
        services.update_delivery(order, actor=request.user, data=data.validated_data)
        return Response(_staff_out(request, order))


class AdminOrderCompleteView(APIView):
    permission_classes = [IsOrderDesk]

    @extend_schema(operation_id="admin_order_complete", request=None, responses=AdminOrderSerializer)
    def post(self, request: Request, number: str) -> Response:
        order = services.complete(_staff_order(request, number), actor=request.user)
        return Response(_staff_out(request, order))

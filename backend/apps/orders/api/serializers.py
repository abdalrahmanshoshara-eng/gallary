from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import quote

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Governorate
from apps.artworks.api.serializers import PublicArtworkImageSerializer, _primary
from apps.core.models import SiteSetting

from .. import policy
from ..models import (
    DeliveryMethod,
    DeliveryStatus,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
    PaymentKind,
    PaymentMethod,
    PaymentRecord,
    PaymentRecordStatus,
)


def whatsapp_url(order: Order, settings_row: SiteSetting | None = None) -> str | None:
    """BR-312: a deep link the customer opens and sends themselves. Never claims "sent"."""
    number = re.sub(r"\D", "", (settings_row or SiteSetting.load()).whatsapp_number or "")
    if not number:
        return None
    text = (
        f"مرحباً، أود إتمام الطلب رقم {order.order_number}.\n"
        f"العربون المطلوب: {order.deposit_due} USD — الإجمالي: {order.subtotal} USD."
    )
    return f"https://wa.me/{number}?text={quote(text)}"


class OrderItemSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    artwork_slug = serializers.CharField(source="artwork.slug")
    title = serializers.CharField(source="title_snapshot")
    unit_price = serializers.DecimalField(source="unit_price_snapshot", max_digits=12, decimal_places=2)
    image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "artwork_slug", "title", "image", "quantity", "unit_price", "line_total", "status"]
        read_only_fields = fields

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_image(self, item: OrderItem):
        return _primary(item.artwork)


class StatusStepSerializer(serializers.Serializer):
    status = serializers.CharField()
    at = serializers.DateTimeField()


class DeliveryPublicSerializer(serializers.Serializer):
    status = serializers.CharField()
    method = serializers.CharField()
    delivered_at = serializers.DateTimeField(allow_null=True)


class OrderSummarySerializer(serializers.ModelSerializer):
    number = serializers.CharField(source="order_number")
    item_count = serializers.SerializerMethodField()
    needs_action = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "number",
            "source",
            "status",
            "subtotal",
            "deposit_due",
            "amount_paid",
            "item_count",
            "reservation_expires_at",
            "needs_action",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_count(self, order: Order) -> int:
        return sum(1 for i in order.items.all() if i.status == OrderItemStatus.ACTIVE)

    def get_needs_action(self, order: Order) -> bool:
        return order.status == OrderStatus.PENDING_DEPOSIT


class CustomerOrderSerializer(OrderSummarySerializer):
    items = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    server_now = serializers.SerializerMethodField(
        help_text="Server clock for the countdown (do not trust the device)."
    )
    can_cancel = serializers.SerializerMethodField()
    whatsapp_url = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()

    class Meta(OrderSummarySerializer.Meta):
        fields = [
            *OrderSummarySerializer.Meta.fields,
            "deposit_status",
            "payment_status",
            "remaining",
            "server_now",
            "can_cancel",
            "whatsapp_url",
            "contact_name",
            "contact_phone",
            "contact_email",
            "governorate",
            "city",
            "address_line",
            "customer_notes",
            "cancelled_reason",
            "items",
            "history",
            "delivery",
        ]
        read_only_fields = fields

    @extend_schema_field(OrderItemSerializer(many=True))
    def get_items(self, order: Order):
        return OrderItemSerializer([i for i in order.items.all() if i.status == OrderItemStatus.ACTIVE], many=True).data

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_remaining(self, order: Order):
        return f"{max(order.subtotal - order.amount_paid, 0):.2f}"

    def get_server_now(self, order: Order) -> str:
        return timezone.now().isoformat()

    def get_can_cancel(self, order: Order) -> bool:
        return order.source != "auction" and order.status == OrderStatus.PENDING_DEPOSIT and order.amount_paid == 0

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_whatsapp_url(self, order: Order):
        if order.is_final:
            return None
        return whatsapp_url(order, self.context.get("settings"))

    @extend_schema_field(StatusStepSerializer(many=True))
    def get_history(self, order: Order):
        return [{"status": h.to_status, "at": h.created_at} for h in order.history.all()]

    @extend_schema_field(DeliveryPublicSerializer(allow_null=True))
    def get_delivery(self, order: Order):
        d = getattr(order, "delivery", None)
        return None if d is None else {"status": d.status, "method": d.method, "delivered_at": d.delivered_at}


class PolicySerializer(serializers.Serializer):
    version = serializers.CharField()
    title = serializers.CharField()
    points = serializers.ListField(child=serializers.CharField())
    reservation_hours = serializers.IntegerField()


def policy_payload() -> dict:
    return {
        "version": policy.VERSION,
        "title": policy.TITLE,
        "points": policy.POINTS,
        "reservation_hours": policy.RESERVATION_HOURS,
    }


class CheckoutSerializer(serializers.Serializer):
    policy_version = serializers.CharField(max_length=20)
    accept_policy = serializers.BooleanField()
    governorate = serializers.ChoiceField(choices=Governorate.choices)
    city = serializers.CharField(max_length=100)
    address_line = serializers.CharField(max_length=255)
    customer_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")

    def validate_accept_policy(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("يجب الموافقة على سياسة العربون والإلغاء.")
        return value


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


# --- staff ------------------------------------------------------------------------------------------
class PaymentRecordSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    recorded_by = serializers.CharField(source="recorded_by.display_name", read_only=True)
    confirmed_by = serializers.CharField(source="confirmed_by.display_name", read_only=True, default=None)

    class Meta:
        model = PaymentRecord
        fields = [
            "id",
            "kind",
            "amount",
            "method",
            "reference",
            "notes",
            "status",
            "recorded_by",
            "confirmed_by",
            "confirmed_at",
            "void_reason",
            "created_at",
        ]
        read_only_fields = fields


class AdminOrderItemSerializer(OrderItemSerializer):
    class Meta(OrderItemSerializer.Meta):
        fields = [
            *OrderItemSerializer.Meta.fields,
            "commission_rate_snapshot",
            "commission_amount_snapshot",
            "payee_amount_snapshot",
            "deposit_amount_snapshot",
            "removed_reason",
        ]
        read_only_fields = fields


class HistoryEntrySerializer(serializers.Serializer):
    from_status = serializers.CharField()
    to_status = serializers.CharField()
    actor = serializers.CharField(allow_null=True)
    reason = serializers.CharField()
    created_at = serializers.DateTimeField()


class AdminDeliverySerializer(serializers.Serializer):
    method = serializers.CharField()
    carrier_name = serializers.CharField()
    status = serializers.CharField()
    delivered_at = serializers.DateTimeField(allow_null=True)
    notes = serializers.CharField()


class AvailableActionsSerializer(serializers.Serializer):
    record_payment = serializers.BooleanField(help_text="Money is still owed on an open order")
    record_refund = serializers.BooleanField(help_text="A refund is due (platform cancellation after payment)")
    remove_items = serializers.BooleanField()
    custom_deposit = serializers.BooleanField()
    cancel_by_platform = serializers.BooleanField()
    cancel_for_customer = serializers.BooleanField()
    delivery = serializers.BooleanField()
    complete = serializers.BooleanField()


class AdminOrderListSerializer(OrderSummarySerializer):
    customer = serializers.CharField(source="contact_name")
    phone = serializers.CharField(source="contact_phone")

    class Meta(OrderSummarySerializer.Meta):
        fields = [*OrderSummarySerializer.Meta.fields, "customer", "phone", "deposit_status", "payment_status"]
        read_only_fields = fields


class AdminOrderSerializer(CustomerOrderSerializer):
    customer_id = serializers.UUIDField(source="user.public_id", read_only=True)
    items = serializers.SerializerMethodField()
    payments = PaymentRecordSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta(CustomerOrderSerializer.Meta):
        fields = [
            *CustomerOrderSerializer.Meta.fields,
            "customer_id",
            "deposit_type",
            "internal_notes",
            "policy_version",
            "policy_accepted_at",
            "confirmed_at",
            "closed_at",
            "payments",
            "actions",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminOrderItemSerializer(many=True))
    def get_items(self, order: Order):
        return AdminOrderItemSerializer(order.items.all(), many=True).data

    @extend_schema_field(HistoryEntrySerializer(many=True))
    def get_history(self, order: Order):
        return [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "actor": (h.actor.display_name or h.actor.phone) if h.actor else None,
                "reason": h.reason,
                "created_at": h.created_at,
            }
            for h in order.history.all()
        ]

    @extend_schema_field(AdminDeliverySerializer)
    def get_delivery(self, order: Order):
        d = order.delivery
        return {
            "method": d.method,
            "carrier_name": d.carrier_name,
            "status": d.status,
            "delivered_at": d.delivered_at,
            "notes": d.notes,
        }

    @extend_schema_field(AvailableActionsSerializer)
    def get_actions(self, order: Order):
        s = order.status
        is_super = bool(self.context.get("is_super_admin"))
        before_deposit = s == OrderStatus.PENDING_DEPOSIT
        paid_stage = s in (OrderStatus.DEPOSIT_CONFIRMED, OrderStatus.PAYMENT_PENDING)
        active = sum(1 for i in order.items.all() if i.status == OrderItemStatus.ACTIVE)
        return {
            "record_payment": not order.is_final and order.amount_paid < order.subtotal,
            "record_refund": order.deposit_status == "refund_due" and order.amount_paid > 0,
            "remove_items": before_deposit and active > 1,
            "custom_deposit": before_deposit and is_super,
            "cancel_by_platform": not order.is_final,
            "cancel_for_customer": paid_stage,
            "delivery": paid_stage or s == OrderStatus.CONFIRMED,
            "complete": s == OrderStatus.CONFIRMED and order.delivery.status == DeliveryStatus.DELIVERED,
        }


class PaymentInputSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=PaymentKind.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    confirm = serializers.BooleanField(default=True)


class OrderReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, allow_blank=True)


class StaffCancelSerializer(OrderReasonSerializer):
    kind = serializers.ChoiceField(choices=[("platform", "platform"), ("customer", "customer")])


class CustomDepositSerializer(OrderReasonSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class DeliveryInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=DeliveryMethod.choices, required=False, allow_blank=True)
    carrier_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=DeliveryStatus.choices, required=False)
    delivered_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class NotesSerializer(serializers.Serializer):
    internal_notes = serializers.CharField(allow_blank=True)


PAYMENT_RECORD_STATUSES = PaymentRecordStatus

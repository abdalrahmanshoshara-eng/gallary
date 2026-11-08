from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOrdersStaff
from apps.core import idempotency
from apps.core.errors import ConflictError

from .. import selectors, services
from ..models import Settlement, SettlementStatus
from .serializers import (
    PayeeDueSerializer,
    PayInputSerializer,
    SettlementReasonSerializer,
    SettlementSerializer,
    SettlementSummarySerializer,
)

IDEMPOTENCY_HEADER = OpenApiParameter(
    "Idempotency-Key", str, location=OpenApiParameter.HEADER, required=True, description="UUID per attempt"
)


class SettlementListView(ListAPIView):
    permission_classes = [IsOrdersStaff]
    serializer_class = SettlementSerializer

    def get_queryset(self):
        p = self.request.query_params
        return selectors.staff_settlements(
            status=p.get("status", ""), search=p.get("search", ""), payee=p.get("payee", "")
        )

    @extend_schema(
        operation_id="admin_settlements_list",
        parameters=[
            OpenApiParameter("status", str, enum=[*SettlementStatus.values, "all"]),
            OpenApiParameter("search", str),
            OpenApiParameter("payee", str, description="payee_key from the by-payee summary"),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class SettlementSummaryView(APIView):
    permission_classes = [IsOrdersStaff]

    @extend_schema(operation_id="admin_settlements_summary", responses=SettlementSummarySerializer)
    def get(self, request: Request) -> Response:
        return Response(SettlementSummarySerializer(selectors.summary()).data)


class SettlementPayeesView(APIView):
    permission_classes = [IsOrdersStaff]

    @extend_schema(operation_id="admin_settlements_payees", responses=PayeeDueSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PayeeDueSerializer(selectors.pending_by_payee(), many=True).data)


class SettlementPayView(APIView):
    permission_classes = [IsOrdersStaff]

    @extend_schema(
        operation_id="admin_settlements_pay",
        request=PayInputSerializer,
        responses=SettlementSerializer(many=True),
        parameters=[IDEMPOTENCY_HEADER],
    )
    def post(self, request: Request) -> Response:
        data = PayInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data

        def action():
            chosen = list(Settlement.objects.filter(public_id__in=v["settlements"]))
            if len(chosen) != len(set(v["settlements"])):
                raise ConflictError(
                    "بعض التسويات غير موجودة.", code="VALIDATION_ERROR", http_status=400, details={"settlements": ["?"]}
                )
            paid = services.pay(
                chosen, actor=request.user, reference=v["reference"], paid_at=v["paid_at"], notes=v["notes"]
            )
            rows = selectors.staff_settlements().filter(pk__in=[s.pk for s in paid])
            return 200, SettlementSerializer(rows, many=True).data

        code, body = idempotency.run_once(request, scope="settlement_pay", action=action)
        return Response(body, status=code)


def _one(public_id) -> Settlement:
    return get_object_or_404(Settlement, public_id=public_id)


def _out(settlement: Settlement) -> dict:
    return SettlementSerializer(selectors.staff_settlements().get(pk=settlement.pk)).data


class SettlementHoldView(APIView):
    permission_classes = [IsOrdersStaff]

    @extend_schema(
        operation_id="admin_settlements_hold", request=SettlementReasonSerializer, responses=SettlementSerializer
    )
    def post(self, request: Request, public_id) -> Response:
        data = SettlementReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(_out(services.hold(_one(public_id), actor=request.user, reason=data.validated_data["reason"])))


class SettlementReleaseView(APIView):
    permission_classes = [IsOrdersStaff]

    @extend_schema(operation_id="admin_settlements_release", request=None, responses=SettlementSerializer)
    def post(self, request: Request, public_id) -> Response:
        return Response(_out(services.release(_one(public_id), actor=request.user)))


class SettlementCancelView(APIView):
    permission_classes = [IsOrdersStaff]

    @extend_schema(
        operation_id="admin_settlements_cancel", request=SettlementReasonSerializer, responses=SettlementSerializer
    )
    def post(self, request: Request, public_id) -> Response:
        data = SettlementReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            _out(services.cancel(_one(public_id), actor=request.user, reason=data.validated_data["reason"]))
        )

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.orders.models import OrderStatus

from .. import services
from ..models import Settlement


class SettlementSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    order_number = serializers.CharField(source="order_item.order.order_number")
    artwork_title = serializers.CharField(source="order_item.title_snapshot")
    artwork_id = serializers.UUIDField(source="order_item.artwork.public_id")
    quantity = serializers.IntegerField(source="order_item.quantity")
    paid_by = serializers.CharField(source="paid_by.display_name", allow_null=True, default=None)
    actions = serializers.SerializerMethodField()
    order_cancelled_after_payment = serializers.SerializerMethodField(
        help_text="Paid, then the order was cancelled: recover the amount from the payee outside the platform."
    )

    class Meta:
        model = Settlement
        fields = [
            "id",
            "order_number",
            "artwork_title",
            "artwork_id",
            "quantity",
            "payee_type",
            "payee_name",
            "payee_key",
            "currency",
            "gross_amount",
            "commission_rate",
            "platform_commission",
            "payee_amount",
            "status",
            "status_reason",
            "paid_at",
            "reference",
            "notes",
            "paid_by",
            "actions",
            "order_cancelled_after_payment",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(
        serializers.ListField(child=serializers.ChoiceField(choices=["pay", "hold", "release", "cancel"]))
    )
    def get_actions(self, settlement: Settlement):
        return services.available_actions(settlement)

    def get_order_cancelled_after_payment(self, settlement: Settlement) -> bool:
        return settlement.status == "paid" and settlement.order_item.order.status == OrderStatus.CANCELLED_BY_PLATFORM


class TotalSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class SettlementSummarySerializer(serializers.Serializer):
    pending = TotalSerializer()
    on_hold = TotalSerializer()
    paid_this_month = TotalSerializer()


class PayeeDueSerializer(serializers.Serializer):
    payee_key = serializers.CharField()
    payee_name = serializers.CharField()
    payee_type = serializers.CharField()
    count = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    oldest = serializers.DateTimeField()


class PayInputSerializer(serializers.Serializer):
    settlements = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=200)
    reference = serializers.CharField(max_length=120, allow_blank=True)
    paid_at = serializers.DateField(default=timezone.localdate)
    notes = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)


class SettlementReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, allow_blank=True)

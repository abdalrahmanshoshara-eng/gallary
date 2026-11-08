from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaff

from .. import selectors


class CatalogKpis(serializers.Serializer):
    published_artworks = serializers.IntegerField()
    available_artworks = serializers.IntegerField()


class OrderKpis(serializers.Serializer):
    orders = serializers.IntegerField()
    pending_deposit = serializers.IntegerField()
    sales_count = serializers.IntegerField()
    sales_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    commission_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class SettlementKpis(serializers.Serializer):
    pending_count = serializers.IntegerField()
    pending_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class AuctionKpis(serializers.Serializer):
    live = serializers.IntegerField()
    upcoming = serializers.IntegerField()
    ended = serializers.IntegerField()


class AttentionItem(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=["order_expiring", "settlements_on_hold", "auction_awaiting_winner", "auction_requests_new"]
    )
    ref = serializers.CharField()
    label = serializers.CharField()
    at = serializers.DateTimeField(allow_null=True)
    count = serializers.IntegerField(required=False)


class DashboardSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=list(selectors.PERIODS))
    generated_at = serializers.DateTimeField()
    catalog = CatalogKpis(allow_null=True)
    orders = OrderKpis(allow_null=True)
    settlements = SettlementKpis(allow_null=True)
    auctions = AuctionKpis(allow_null=True)
    attention = AttentionItem(many=True)


class DashboardView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        operation_id="admin_dashboard",
        parameters=[OpenApiParameter("period", str, enum=list(selectors.PERIODS), default="30d")],
        responses=DashboardSerializer,
    )
    def get(self, request: Request) -> Response:
        data = selectors.dashboard(request.user, request.query_params.get("period", "30d"))
        return Response(DashboardSerializer(data).data)

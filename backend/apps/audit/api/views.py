from __future__ import annotations

from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperAdmin

from ..models import AuditLog


class AuditEntrySerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    actor_phone = serializers.CharField(source="actor.phone", allow_null=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_phone",
            "action",
            "entity_type",
            "entity_id",
            "changes",
            "reason",
            "ip",
            "request_id",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor(self, entry: AuditLog) -> str | None:
        return (entry.actor.display_name or entry.actor.phone) if entry.actor_id else None


def _date(value: str, end: bool):
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return timezone.make_aware(datetime.combine(day, time.max if end else time.min))


class AuditLogListView(ListAPIView):
    """BR-007: read-only for the Super Admin. Newest first."""

    permission_classes = [IsSuperAdmin]
    serializer_class = AuditEntrySerializer

    def get_queryset(self):
        p = self.request.query_params
        qs = AuditLog.objects.select_related("actor")
        if p.get("entity_type"):
            qs = qs.filter(entity_type=p["entity_type"])
        if p.get("action"):
            qs = qs.filter(action__startswith=p["action"].strip())
        if p.get("actor", "").strip():
            term = p["actor"].strip()
            qs = qs.filter(Q(actor__display_name__icontains=term) | Q(actor__phone__icontains=term.lstrip("0")))
        if p.get("system") == "1":
            qs = qs.filter(actor__isnull=True)
        start, end = _date(p.get("from", ""), False), _date(p.get("to", ""), True)
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)
        if p.get("search", "").strip():
            term = p["search"].strip()
            qs = qs.filter(Q(entity_id__icontains=term) | Q(reason__icontains=term) | Q(request_id=term))
        return qs.order_by("-created_at", "-id")

    @extend_schema(
        operation_id="admin_audit_list",
        parameters=[
            OpenApiParameter("entity_type", str),
            OpenApiParameter("action", str, description="prefix, e.g. settlement."),
            OpenApiParameter("actor", str),
            OpenApiParameter("system", str, enum=["1"]),
            OpenApiParameter("from", str, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, description="YYYY-MM-DD"),
            OpenApiParameter("search", str),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class AuditFacetsSerializer(serializers.Serializer):
    entity_types = serializers.ListField(child=serializers.CharField())


class AuditFacetsView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(operation_id="admin_audit_facets", responses=AuditFacetsSerializer)
    def get(self, request: Request) -> Response:
        types = AuditLog.objects.order_by("entity_type").values_list("entity_type", flat=True).distinct()
        return Response({"entity_types": list(types)})

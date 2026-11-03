"""Liveness and readiness endpoints (public, unthrottled, never cached)."""

from __future__ import annotations

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.health import run_checks

from .serializers import LivenessSerializer, ReadinessSerializer


@method_decorator(never_cache, name="dispatch")
class LivenessView(APIView):
    """The process is up and can serve requests. No dependency checks."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    @extend_schema(operation_id="health_live", responses=LivenessSerializer)
    def get(self, request: Request) -> Response:
        return Response(LivenessSerializer({"status": "ok", "server_time": timezone.now()}).data)


@method_decorator(never_cache, name="dispatch")
class ReadinessView(APIView):
    """All critical dependencies are reachable. Returns 503 otherwise."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    @extend_schema(operation_id="health_ready", responses={200: ReadinessSerializer, 503: ReadinessSerializer})
    def get(self, request: Request) -> Response:
        ready, results = run_checks()
        body = ReadinessSerializer(
            {
                "status": "ready" if ready else "not_ready",
                "server_time": timezone.now(),
                "checks": [r.as_dict() for r in results],
            }
        ).data
        return Response(body, status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE)

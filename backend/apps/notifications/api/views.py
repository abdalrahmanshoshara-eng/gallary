"""The signed-in user's notifications (any account type) and their e-mail preference."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import selectors, services
from ..channels import email_enabled
from ..models import Notification
from .serializers import NotificationSerializer, PreferencesSerializer, ReadAllSerializer, UnreadCountSerializer


class NotificationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return selectors.for_user(self.request.user, unread=self.request.query_params.get("unread") == "1")

    @extend_schema(
        operation_id="notifications_list",
        parameters=[OpenApiParameter("unread", OpenApiTypes.STR, description="`1` = unread only")],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="notifications_unread_count", responses=UnreadCountSerializer)
    def get(self, request: Request) -> Response:
        return Response({"unread": selectors.unread_count(request.user)})


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="notifications_read", request=None, responses=NotificationSerializer)
    def post(self, request: Request, public_id) -> Response:
        notification = get_object_or_404(Notification, public_id=public_id, user=request.user)
        return Response(NotificationSerializer(services.mark_read(request.user, notification)).data)


class ReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="notifications_read_all", request=None, responses=ReadAllSerializer)
    def post(self, request: Request) -> Response:
        updated = services.mark_all_read(request.user)
        return Response({"updated": updated, "unread": 0})


class PreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, user) -> dict:
        return {
            "email_enabled": services.preference(user).email_enabled,
            "email_available": email_enabled(),
            "has_email": bool(user.email),
        }

    @extend_schema(operation_id="notifications_preferences", responses=PreferencesSerializer)
    def get(self, request: Request) -> Response:
        return Response(self._payload(request.user))

    @extend_schema(
        operation_id="notifications_preferences_update", request=PreferencesSerializer, responses=PreferencesSerializer
    )
    def patch(self, request: Request) -> Response:
        data = PreferencesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_email_enabled(request.user, data.validated_data["email_enabled"])
        return Response(self._payload(request.user))

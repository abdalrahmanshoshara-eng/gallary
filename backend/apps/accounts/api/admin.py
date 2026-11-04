"""Super Admin user and staff management (/api/v1/admin/...). BR-907."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.http import client_ip

from .. import selectors
from ..errors import SelfModificationError
from ..models import User
from ..permissions import IsSuperAdmin
from ..roles import Role
from ..services import auth as auth_service
from ..services import users as user_service
from .serializers import (
    ActivationSerializer,
    AdminSetPasswordSerializer,
    AdminUserSerializer,
    RevokedCountSerializer,
    RoleSerializer,
    StaffCreateSerializer,
    StaffUpdateSerializer,
)


class RoleListView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(operation_id="admin_roles_list", responses=RoleSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response([{"value": r.value, "label": r.label} for r in Role])


class StaffListCreateView(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AdminUserSerializer
    pagination_class = None

    def get_queryset(self):
        return selectors.staff_users()

    @extend_schema(operation_id="admin_staff_list")
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="admin_staff_create", request=StaffCreateSerializer, responses={201: AdminUserSerializer}
    )
    def post(self, request: Request) -> Response:
        data = StaffCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = user_service.create_staff(
            actor=request.user,
            raw_phone=data.validated_data["phone"],
            display_name=data.validated_data["display_name"],
            roles=data.validated_data["roles"],
            ip=client_ip(request),
            password=data.validated_data["password"] or None,
        )
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


class StaffDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(operation_id="admin_staff_update", request=StaffUpdateSerializer, responses=AdminUserSerializer)
    def patch(self, request: Request, public_id: str) -> Response:
        target = get_object_or_404(User, public_id=public_id)
        data = StaffUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        user = user_service.update_staff(
            actor=request.user,
            target=target,
            display_name=data.validated_data.get("display_name"),
            roles=data.validated_data.get("roles"),
            ip=client_ip(request),
        )
        return Response(AdminUserSerializer(user).data)

    @extend_schema(operation_id="admin_staff_revoke_access", responses=AdminUserSerializer)
    def delete(self, request: Request, public_id: str) -> Response:
        target = get_object_or_404(User, public_id=public_id)
        user = user_service.revoke_staff_access(actor=request.user, target=target, ip=client_ip(request))
        return Response(AdminUserSerializer(user).data)


class UserListView(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        params = self.request.query_params
        active = params.get("is_active")
        return selectors.search_users(
            search=params.get("search", ""),
            kind=params.get("kind", ""),
            is_active={"true": True, "false": False}.get(active) if active else None,
        )

    @extend_schema(
        operation_id="admin_users_list",
        parameters=[
            OpenApiParameter("search", OpenApiTypes.STR, description="الاسم أو البريد أو جزء من الرقم"),
            OpenApiParameter("kind", OpenApiTypes.STR, enum=["customer", "staff"]),
            OpenApiParameter("is_active", OpenApiTypes.BOOL),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class _UserActionView(APIView):
    permission_classes = [IsSuperAdmin]

    def target(self, public_id: str) -> User:
        return get_object_or_404(User, public_id=public_id)


class UserActivateView(_UserActionView):
    @extend_schema(operation_id="admin_users_activate", request=ActivationSerializer, responses=AdminUserSerializer)
    def post(self, request: Request, public_id: str) -> Response:
        data = ActivationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = user_service.set_user_active(
            actor=request.user,
            target=self.target(public_id),
            active=True,
            reason=data.validated_data["reason"],
            ip=client_ip(request),
        )
        return Response(AdminUserSerializer(user).data)


class UserDeactivateView(_UserActionView):
    @extend_schema(operation_id="admin_users_deactivate", request=ActivationSerializer, responses=AdminUserSerializer)
    def post(self, request: Request, public_id: str) -> Response:
        data = ActivationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = user_service.set_user_active(
            actor=request.user,
            target=self.target(public_id),
            active=False,
            reason=data.validated_data["reason"],
            ip=client_ip(request),
        )
        return Response(AdminUserSerializer(user).data)


class UserRevokeSessionsView(_UserActionView):
    @extend_schema(operation_id="admin_users_revoke_sessions", request=None, responses=RevokedCountSerializer)
    def post(self, request: Request, public_id: str) -> Response:
        count = user_service.admin_revoke_sessions(
            actor=request.user, target=self.target(public_id), ip=client_ip(request)
        )
        return Response({"revoked": count})


class UserSetPasswordView(_UserActionView):
    @extend_schema(operation_id="admin_user_set_password", request=AdminSetPasswordSerializer, responses={204: None})
    def post(self, request: Request, public_id: str) -> Response:
        target = self.target(public_id)
        if target.pk == request.user.pk:
            # Own password goes through /auth/password (requires the current one).
            raise SelfModificationError()
        data = AdminSetPasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        auth_service.admin_set_password(
            actor=request.user, target=target, password=data.validated_data["password"], ip=client_ip(request)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

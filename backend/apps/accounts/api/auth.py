"""Customer-facing authentication endpoints (/api/v1/auth/...)."""

from __future__ import annotations

from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.http import client_ip

from .. import selectors
from ..models import SessionRevokeReason, UserSession
from ..otp.senders import get_otp_sender
from ..services import otp as otp_service
from ..services import sessions as session_service
from ..services import users as user_service
from .serializers import (
    LoginResultSerializer,
    MeSerializer,
    OtpRequestedSerializer,
    PhoneInputSerializer,
    ProfileUpdateSerializer,
    RevokedCountSerializer,
    SessionSerializer,
    VerifyInputSerializer,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie. The frontend calls it before the first unsafe request."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(operation_id="auth_csrf", responses={204: None})
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


# Login endpoints require the CSRF token too (protects against login CSRF).
@method_decorator(csrf_protect, name="dispatch")
class OtpRequestView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        operation_id="auth_otp_request", request=PhoneInputSerializer, responses={202: OtpRequestedSerializer}
    )
    def post(self, request: Request) -> Response:
        data = PhoneInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = otp_service.request_otp(raw_phone=data.validated_data["phone"], ip=client_ip(request))
        body = {
            "phone": result.phone,
            "expires_in_seconds": result.expires_in_seconds,
            "resend_after_seconds": result.resend_after_seconds,
            "channel": get_otp_sender().channel,
        }
        return Response(OtpRequestedSerializer(body).data, status=status.HTTP_202_ACCEPTED)


@method_decorator(csrf_protect, name="dispatch")
class OtpVerifyView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(operation_id="auth_otp_verify", request=VerifyInputSerializer, responses=LoginResultSerializer)
    def post(self, request: Request) -> Response:
        data = VerifyInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user, created = otp_service.verify_otp(raw_phone=data.validated_data["phone"], code=data.validated_data["code"])
        # login() rotates the session key (BR-910); the user_logged_in signal tracks it.
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(LoginResultSerializer({"user": user, "created": created}).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="auth_logout", request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="auth_me", responses=MeSerializer)
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)

    @extend_schema(operation_id="auth_me_update", request=ProfileUpdateSerializer, responses=MeSerializer)
    def patch(self, request: Request) -> Response:
        data = ProfileUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        user = user_service.update_profile(request.user, **data.validated_data)
        return Response(MeSerializer(user).data)


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="auth_sessions_list", responses=SessionSerializer(many=True))
    def get(self, request: Request) -> Response:
        sessions = selectors.active_sessions_for(request.user)
        context = {"current_session_id": session_service.current_session_id(request._request)}
        return Response(SessionSerializer(sessions, many=True, context=context).data)


class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="auth_sessions_revoke", responses={204: None})
    def delete(self, request: Request, public_id: str) -> Response:
        # Scoped to the requesting user: other users' sessions are simply "not found" (IDOR).
        tracked = get_object_or_404(UserSession, public_id=public_id, user=request.user)
        if str(tracked.public_id) == session_service.current_session_id(request._request):
            logout(request._request)
        else:
            session_service.revoke_session(tracked, SessionRevokeReason.REVOKED_BY_USER)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevokeOtherSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="auth_sessions_revoke_others", request=None, responses=RevokedCountSerializer)
    def post(self, request: Request) -> Response:
        count = session_service.revoke_user_sessions(
            request.user,
            SessionRevokeReason.LOGOUT_OTHERS,
            except_public_id=session_service.current_session_id(request._request),
        )
        return Response({"revoked": count})

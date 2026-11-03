import pytest
from django.test import override_settings
from django.urls import path
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errors import ConflictError


class _InputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)


class ValidatingView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        _InputSerializer(data=request.data).is_valid(raise_exception=True)
        return Response({})


class ConflictView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raise ConflictError("العمل غير متاح.", code="LISTING_UNAVAILABLE", details={"listing": "x"})


class PrivateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({})


class CrashView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise RuntimeError("unexpected")


urlpatterns = [
    path("api/v1/t/validate", ValidatingView.as_view()),
    path("api/v1/t/conflict", ConflictView.as_view()),
    path("api/v1/t/private", PrivateView.as_view()),
    path("api/v1/t/crash", CrashView.as_view()),
]
handler404 = "apps.core.exceptions.handler404"
handler500 = "apps.core.exceptions.handler500"

pytestmark = pytest.mark.urls("apps.core.tests.test_errors")


def assert_envelope(response, status, code):
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["request_id"] == response["X-Request-ID"]
    return error


def test_validation_error_keeps_field_details(api_client):
    error = assert_envelope(api_client.post("/api/v1/t/validate", {"amount": "0"}), 400, "VALIDATION_ERROR")
    assert "amount" in error["details"]


def test_app_error_maps_code_message_and_details(api_client):
    error = assert_envelope(api_client.post("/api/v1/t/conflict"), 409, "LISTING_UNAVAILABLE")
    assert error["message"] == "العمل غير متاح."
    assert error["details"] == {"listing": "x"}


@pytest.mark.django_db
def test_unauthenticated_request_is_rejected(api_client):
    assert_envelope(api_client.get("/api/v1/t/private"), 403, "NOT_AUTHENTICATED")


def test_unknown_api_path_returns_json_404(client):
    assert_envelope(client.get("/api/v1/does-not-exist"), 404, "NOT_FOUND")


@override_settings(DEBUG=False)
def test_unhandled_exception_returns_generic_json_500(client):
    client.raise_request_exception = False
    response = client.get("/api/v1/t/crash")
    error = assert_envelope(response, 500, "SERVER_ERROR")
    assert "unexpected" not in error["message"]


@pytest.mark.urls("config.urls")
@pytest.mark.parametrize("debug", [True, False])
def test_unknown_api_path_is_json_in_every_environment(client, settings, debug):
    settings.DEBUG = debug
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

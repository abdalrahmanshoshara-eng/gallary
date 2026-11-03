"""Unified API error envelope for DRF and plain Django error handlers."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, JsonResponse
from django.views import defaults
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .errors import AppError
from .request_context import get_request_id

logger = logging.getLogger(__name__)

# DRF exception class -> (code, Arabic message). Validation keeps its field details.
_DRF_ERRORS: dict[type[exceptions.APIException], tuple[str, str]] = {
    exceptions.NotAuthenticated: ("NOT_AUTHENTICATED", "يجب تسجيل الدخول أولاً."),
    exceptions.AuthenticationFailed: ("AUTHENTICATION_FAILED", "تعذّر التحقق من هويتك."),
    exceptions.PermissionDenied: ("PERMISSION_DENIED", "ليست لديك صلاحية لتنفيذ هذه العملية."),
    exceptions.NotFound: ("NOT_FOUND", "العنصر المطلوب غير موجود."),
    exceptions.MethodNotAllowed: ("METHOD_NOT_ALLOWED", "طريقة الطلب غير مسموحة."),
    exceptions.NotAcceptable: ("NOT_ACCEPTABLE", "صيغة الاستجابة المطلوبة غير مدعومة."),
    exceptions.UnsupportedMediaType: ("UNSUPPORTED_MEDIA_TYPE", "نوع المحتوى غير مدعوم."),
    exceptions.Throttled: ("THROTTLED", "طلبات كثيرة خلال وقت قصير. حاول لاحقاً."),
    exceptions.ParseError: ("PARSE_ERROR", "تعذّرت قراءة البيانات المرسلة."),
    exceptions.ValidationError: ("VALIDATION_ERROR", "البيانات المدخلة غير صالحة."),
}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
            "request_id": get_request_id(),
        }
    }


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, AppError):
        return Response(error_body(exc.code, exc.message, exc.details), status=exc.http_status)

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled: let Django's 500 handling log it with the traceback.
        return None

    code, message = "ERROR", "تعذّر تنفيذ الطلب."
    for exc_class, mapped in _DRF_ERRORS.items():
        if isinstance(exc, exc_class):
            code, message = mapped
            break

    details: Any = {}
    if isinstance(exc, exceptions.ValidationError):
        details = response.data if isinstance(response.data, dict) else {"non_field_errors": response.data}
    elif isinstance(exc, exceptions.Throttled) and exc.wait is not None:
        details = {"retry_after_seconds": int(exc.wait)}

    response.data = error_body(code, message, details)
    return response


def _is_api(request: HttpRequest) -> bool:
    return request.path.startswith("/api/")


def api_not_found(request: HttpRequest, path: str = "") -> JsonResponse:
    """Catch-all for unknown /api/ paths: JSON in every environment, including DEBUG."""
    return JsonResponse(
        error_body("NOT_FOUND", "المسار المطلوب غير موجود."),
        status=status.HTTP_404_NOT_FOUND,
        json_dumps_params={"ensure_ascii": False},
    )


def handler404(request: HttpRequest, exception: Exception | None = None):
    if _is_api(request):
        return JsonResponse(
            error_body("NOT_FOUND", "المسار المطلوب غير موجود."),
            status=status.HTTP_404_NOT_FOUND,
            json_dumps_params={"ensure_ascii": False},
        )
    return defaults.page_not_found(request, exception)


def handler500(request: HttpRequest):
    if _is_api(request):
        return JsonResponse(
            error_body("SERVER_ERROR", "حدث خطأ غير متوقع. حاول مرة أخرى لاحقاً."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            json_dumps_params={"ensure_ascii": False},
        )
    return defaults.server_error(request)

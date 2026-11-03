"""
Application errors.

Services raise `AppError` subclasses with a stable machine-readable `code` and an Arabic
user-facing message. The API exception handler turns them into the unified envelope:

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

from typing import Any

from rest_framework import status


class AppError(Exception):
    code: str = "APP_ERROR"
    message: str = "تعذّر تنفيذ العملية."
    http_status: int = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        if http_status is not None:
            self.http_status = http_status
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    message = "العنصر المطلوب غير موجود."
    http_status = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    """State conflicts, e.g. an invalid status transition or unavailable stock."""

    code = "CONFLICT"
    message = "تعارض في حالة البيانات."
    http_status = status.HTTP_409_CONFLICT


class PermissionDeniedError(AppError):
    code = "PERMISSION_DENIED"
    message = "ليست لديك صلاحية لتنفيذ هذه العملية."
    http_status = status.HTTP_403_FORBIDDEN

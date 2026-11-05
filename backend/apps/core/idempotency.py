"""
Idempotent execution of sensitive POSTs (checkout, payments).

    result = run_once(request, scope="checkout", action=lambda: (201, {...}))

The record is written in the same transaction as the action, so either both exist or neither.
A concurrent duplicate hits the unique constraint and returns the stored result.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from django.db import IntegrityError, transaction
from rest_framework import status

from .errors import AppError
from .models import IdempotencyRecord

HEADER = "HTTP_IDEMPOTENCY_KEY"
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class IdempotencyKeyRequired(AppError):
    code = "IDEMPOTENCY_KEY_REQUIRED"
    message = "طلب غير صالح: مفتاح منع التكرار مفقود. أعد تحميل الصفحة وحاول مجدداً."
    http_status = status.HTTP_400_BAD_REQUEST


def key_from(request) -> str:
    key = (request.META.get(HEADER) or "").strip()
    if not _KEY_RE.match(key):
        raise IdempotencyKeyRequired()
    return key


def run_once(request, *, scope: str, action: Callable[[], tuple[int, dict]]) -> tuple[int, dict]:
    key = key_from(request)
    user = request.user
    existing = IdempotencyRecord.objects.filter(user=user, scope=scope, key=key).first()
    if existing is not None:
        return existing.status_code, existing.response
    try:
        with transaction.atomic():
            code, body = action()
            IdempotencyRecord.objects.create(user=user, scope=scope, key=key, status_code=code, response=body)
            return code, body
    except IntegrityError:
        existing = IdempotencyRecord.objects.filter(user=user, scope=scope, key=key).first()
        if existing is None:
            raise
        return existing.status_code, existing.response

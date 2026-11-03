"""OTP request and verification (BR-901…905)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from ..errors import AccountDisabledError, OtpExpiredError, OtpInvalidError, OtpRateLimitedError, OtpUnavailableError
from ..models import OtpChallenge, User
from ..otp.crypto import code_matches, generate_code, hash_code, seal
from ..otp.senders import get_otp_sender
from ..phone import normalize_phone
from ..tasks import deliver_otp


@dataclass(frozen=True)
class OtpRequested:
    phone: str
    expires_in_seconds: int
    resend_after_seconds: int


def _lock_phone(phone: str) -> None:
    """Serialise OTP requests per phone for the rest of the transaction (pgbouncer-safe)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"otp:{phone}"])


def _retry_after(oldest_in_window, window: timedelta, now) -> int:
    return max(1, math.ceil((oldest_in_window + window - now).total_seconds()))


def request_otp(*, raw_phone: str, ip: str | None) -> OtpRequested:
    """
    Issue a new code and queue its delivery.

    The response never reveals whether the phone belongs to an account (BR-905).
    Limits (BR-904): cooldown per phone, hourly cap per phone and per IP.
    """
    phone = normalize_phone(raw_phone)
    sender = get_otp_sender()
    if not sender.available:
        raise OtpUnavailableError()

    now = timezone.now()
    hour = timedelta(hours=1)
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS

    with transaction.atomic():
        _lock_phone(phone)
        recent = OtpChallenge.objects.filter(phone=phone, created_at__gte=now - hour).order_by("created_at")
        last = recent.last()
        if last and (now - last.created_at).total_seconds() < cooldown:
            wait = math.ceil(cooldown - (now - last.created_at).total_seconds())
            raise OtpRateLimitedError(details={"retry_after_seconds": wait})
        if recent.count() >= settings.OTP_MAX_PER_PHONE_PER_HOUR:
            raise OtpRateLimitedError(
                details={"retry_after_seconds": _retry_after(recent.first().created_at, hour, now)}
            )
        if ip:
            by_ip = OtpChallenge.objects.filter(request_ip=ip, created_at__gte=now - hour).order_by("created_at")
            if by_ip.count() >= settings.OTP_MAX_PER_IP_PER_HOUR:
                raise OtpRateLimitedError(
                    details={"retry_after_seconds": _retry_after(by_ip.first().created_at, hour, now)}
                )

        # Only the newest code is valid.
        OtpChallenge.objects.filter(phone=phone, consumed_at__isnull=True, invalidated_at__isnull=True).update(
            invalidated_at=now
        )
        code = generate_code()
        challenge = OtpChallenge.objects.create(
            phone=phone,
            code_hash=hash_code(phone, code),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
            request_ip=ip,
            channel=sender.channel,
            provider=sender.name,
            created_at=now,
        )
        sealed = seal(code)
        transaction.on_commit(lambda: deliver_otp.apply_async(args=[challenge.pk, sealed], queue="critical"))

    return OtpRequested(phone=phone, expires_in_seconds=settings.OTP_TTL_SECONDS, resend_after_seconds=cooldown)


_CODE_RE = re.compile(r"^\d+$")


def verify_otp(*, raw_phone: str, code: str) -> tuple[User, bool]:
    """
    Check a code and return (user, created). New phones become customer accounts.

    Wrong attempts are persisted before the error is raised, so the attempt limit holds
    across requests (BR-903).
    """
    phone = normalize_phone(raw_phone)
    code = (code or "").strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if len(code) != settings.OTP_LENGTH or not _CODE_RE.match(code):
        raise OtpInvalidError(details={"code": ["الرمز يتكون من 6 أرقام."]})

    now = timezone.now()
    with transaction.atomic():
        challenge = (
            OtpChallenge.objects.select_for_update()
            .filter(phone=phone, consumed_at__isnull=True, invalidated_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            outcome = "expired"
        else:
            challenge.attempts += 1
            if code_matches(phone, code, challenge.code_hash):
                challenge.consumed_at = now
                outcome = "ok"
            else:
                if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
                    challenge.invalidated_at = now
                outcome = "invalid"
            challenge.save(update_fields=["attempts", "consumed_at", "invalidated_at"])

        if outcome == "ok":
            user = User.objects.filter(phone=phone).first()
            created = user is None
            if created:
                user = User.objects.create_user(phone=phone)

    if outcome == "expired":
        raise OtpExpiredError()
    if outcome == "invalid":
        remaining = max(0, settings.OTP_MAX_ATTEMPTS - challenge.attempts)
        if remaining == 0:
            raise OtpExpiredError("أُدخل الرمز خطأً عدة مرات. اطلب رمزاً جديداً.", details={"remaining_attempts": 0})
        raise OtpInvalidError(details={"remaining_attempts": remaining})
    if not user.is_active:
        raise AccountDisabledError()
    return user, created

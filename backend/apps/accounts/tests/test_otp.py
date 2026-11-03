import logging
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.errors import (
    AccountDisabledError,
    OtpExpiredError,
    OtpInvalidError,
    OtpRateLimitedError,
    OtpUnavailableError,
)
from apps.accounts.models import OtpChallenge, OtpDeliveryStatus, User
from apps.accounts.otp import crypto
from apps.accounts.otp.senders import get_otp_sender
from apps.accounts.services.otp import request_otp, verify_otp

PHONE = "+963944567890"
pytestmark = pytest.mark.django_db


@pytest.fixture
def fixed_code(monkeypatch):
    monkeypatch.setattr("apps.accounts.services.otp.generate_code", lambda: "482913")
    return "482913"


def issue(django_capture_on_commit_callbacks, phone="0944567890", ip="10.0.0.1"):
    with django_capture_on_commit_callbacks(execute=True):
        return request_otp(raw_phone=phone, ip=ip)


# --- storage & delivery -----------------------------------------------------------------
def test_code_is_stored_only_as_hmac_and_delivered(fixed_code, django_capture_on_commit_callbacks, capsys):
    result = issue(django_capture_on_commit_callbacks)
    assert result.phone == PHONE
    challenge = OtpChallenge.objects.get()
    assert fixed_code not in challenge.code_hash
    assert challenge.code_hash == crypto.hash_code(PHONE, fixed_code)
    assert challenge.delivery_status == OtpDeliveryStatus.SENT
    assert challenge.expires_at - challenge.created_at == timedelta(seconds=300)
    assert "code=482913" in capsys.readouterr().out  # console sender (development)


def test_code_never_appears_in_logs(fixed_code, django_capture_on_commit_callbacks, caplog):
    with caplog.at_level(logging.DEBUG):
        issue(django_capture_on_commit_callbacks)
        verify_otp(raw_phone=PHONE, code=fixed_code)
    assert fixed_code not in caplog.text


def test_hash_is_bound_to_the_phone():
    assert crypto.hash_code(PHONE, "111111") != crypto.hash_code("+963998877665", "111111")


def test_sealed_code_expires():
    token = crypto.seal("123456")
    assert crypto.unseal(token) == "123456"
    with freeze_time(timezone.now() + timedelta(seconds=301)), pytest.raises(crypto.SealExpiredError):
        crypto.unseal(token)


@override_settings(OTP_SENDER="disabled")
def test_disabled_sender_returns_unavailable_and_stores_nothing():
    get_otp_sender.cache_clear()
    with pytest.raises(OtpUnavailableError):
        request_otp(raw_phone=PHONE, ip=None)
    assert not OtpChallenge.objects.exists()


# --- limits (BR-904) ----------------------------------------------------------------------
def test_resend_cooldown(django_capture_on_commit_callbacks):
    with freeze_time("2026-11-03 10:00:00"):
        issue(django_capture_on_commit_callbacks)
    with freeze_time("2026-11-03 10:00:30"), pytest.raises(OtpRateLimitedError) as exc:
        issue(django_capture_on_commit_callbacks)
    assert exc.value.details["retry_after_seconds"] == 30
    with freeze_time("2026-11-03 10:01:01"):
        issue(django_capture_on_commit_callbacks)


def test_hourly_cap_per_phone(django_capture_on_commit_callbacks):
    for minute in range(0, 10, 2):  # 5 requests, 2 minutes apart
        with freeze_time(f"2026-11-03 10:{minute:02d}:00"):
            issue(django_capture_on_commit_callbacks)
    with freeze_time("2026-11-03 10:20:00"), pytest.raises(OtpRateLimitedError) as exc:
        issue(django_capture_on_commit_callbacks)
    assert exc.value.details["retry_after_seconds"] == 40 * 60


@override_settings(OTP_MAX_PER_IP_PER_HOUR=3)
def test_hourly_cap_per_ip_across_phones(django_capture_on_commit_callbacks):
    with freeze_time("2026-11-03 10:00:00"):
        for n in range(3):
            issue(django_capture_on_commit_callbacks, phone=f"+96393300000{n}")
        with pytest.raises(OtpRateLimitedError):
            issue(django_capture_on_commit_callbacks, phone="+963933000009")
        issue(django_capture_on_commit_callbacks, phone="+963933000009", ip="10.0.0.2")


def test_new_code_invalidates_previous(monkeypatch, django_capture_on_commit_callbacks):
    codes = iter(["111111", "222222"])
    monkeypatch.setattr("apps.accounts.services.otp.generate_code", lambda: next(codes))
    with freeze_time("2026-11-03 10:00:00"):
        issue(django_capture_on_commit_callbacks)
    with freeze_time("2026-11-03 10:02:00"):
        issue(django_capture_on_commit_callbacks)
        with pytest.raises(OtpInvalidError):
            verify_otp(raw_phone=PHONE, code="111111")
        user, _ = verify_otp(raw_phone=PHONE, code="222222")
    assert user.phone == PHONE


# --- verification -------------------------------------------------------------------------
def test_first_login_creates_customer(fixed_code, django_capture_on_commit_callbacks):
    issue(django_capture_on_commit_callbacks)
    user, created = verify_otp(raw_phone="+963 944 567 890", code=fixed_code)
    assert created and not user.is_staff and not user.has_usable_password()
    assert OtpChallenge.objects.get().consumed_at is not None


def test_existing_user_is_returned(fixed_code, django_capture_on_commit_callbacks, make_user):
    existing = make_user(phone=PHONE)
    issue(django_capture_on_commit_callbacks)
    user, created = verify_otp(raw_phone=PHONE, code=fixed_code)
    assert user == existing and not created
    assert User.objects.count() == 1


def test_code_cannot_be_reused(fixed_code, django_capture_on_commit_callbacks):
    issue(django_capture_on_commit_callbacks)
    verify_otp(raw_phone=PHONE, code=fixed_code)
    with pytest.raises(OtpExpiredError):
        verify_otp(raw_phone=PHONE, code=fixed_code)


def test_wrong_attempts_persist_and_exhaust_the_code(fixed_code, django_capture_on_commit_callbacks):
    issue(django_capture_on_commit_callbacks)
    for remaining in (4, 3, 2, 1):
        with pytest.raises(OtpInvalidError) as exc:
            verify_otp(raw_phone=PHONE, code="000000")
        assert exc.value.details["remaining_attempts"] == remaining
    with pytest.raises(OtpExpiredError):
        verify_otp(raw_phone=PHONE, code="000000")
    # Even the right code is now refused: a new code must be requested.
    with pytest.raises(OtpExpiredError):
        verify_otp(raw_phone=PHONE, code=fixed_code)
    assert OtpChallenge.objects.get().attempts == 5


def test_expired_code_is_refused(fixed_code, django_capture_on_commit_callbacks):
    with freeze_time("2026-11-03 10:00:00"):
        issue(django_capture_on_commit_callbacks)
    with freeze_time("2026-11-03 10:05:01"), pytest.raises(OtpExpiredError):
        verify_otp(raw_phone=PHONE, code=fixed_code)


@pytest.mark.parametrize("bad", ["", "12345", "1234567", "12a456"])
def test_malformed_code_does_not_consume_an_attempt(bad, fixed_code, django_capture_on_commit_callbacks):
    issue(django_capture_on_commit_callbacks)
    with pytest.raises(OtpInvalidError):
        verify_otp(raw_phone=PHONE, code=bad)
    assert OtpChallenge.objects.get().attempts == 0


def test_arabic_indic_digits_are_accepted(fixed_code, django_capture_on_commit_callbacks):
    issue(django_capture_on_commit_callbacks)
    user, _ = verify_otp(raw_phone=PHONE, code="٤٨٢٩١٣")
    assert user.phone == PHONE


def test_deactivated_account_cannot_log_in(fixed_code, django_capture_on_commit_callbacks, make_user):
    make_user(phone=PHONE, active=False)
    issue(django_capture_on_commit_callbacks)
    with pytest.raises(AccountDisabledError):
        verify_otp(raw_phone=PHONE, code=fixed_code)

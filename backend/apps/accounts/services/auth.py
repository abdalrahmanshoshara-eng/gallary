"""
Phone + password authentication for every account (customers, staff, Super Admin).

- Customers register themselves; staff accounts are created by the Super Admin (BR-907).
- Failed logins are counted per phone and per client IP; past the limit the login is locked
  for LOGIN_LOCKOUT_SECONDS. Errors never reveal whether a phone is registered.
- Phone ownership is not verified yet: `phone_verified_at` stays NULL until the WhatsApp
  service is subscribed (BR-901c), then `services.otp.verify_otp` confirms numbers.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import IntegrityError, transaction

from apps.audit import services as audit

from ..errors import (
    AccountDisabledError,
    InvalidCredentialsError,
    LoginLockedError,
    PhoneInUseError,
    WrongPasswordError,
)
from ..models import SessionRevokeReason, User
from ..passwords import check_password_policy
from ..phone import InvalidPhoneError, normalize_phone
from ..roles import Role
from .sessions import revoke_user_sessions
from .users import EmailInUseError


# --- lockout counters ------------------------------------------------------------------------
def _key(kind: str, value: str) -> str:
    return "login-fail:" + kind + ":" + hashlib.sha256(value.encode()).hexdigest()[:32]


def _failures(key: str) -> int:
    return int(cache.get(key) or 0)


def _record_failure(key: str) -> None:
    if not cache.add(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS):
        try:
            cache.incr(key)
        except ValueError:  # expired between add() and incr()
            cache.set(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS)


# Hash used when the phone is unknown, so both paths cost one password check (no timing oracle).
_DUMMY = User(phone="+10000000000")
_DUMMY.set_password("timing-equaliser-not-a-real-password-1")


def login_with_password(*, raw_phone: str, password: str, ip: str | None) -> User:
    try:
        phone = normalize_phone(raw_phone)
    except InvalidPhoneError:
        raise InvalidCredentialsError() from None
    phone_key, ip_key = _key("phone", phone), _key("ip", ip or "-")
    if (
        _failures(phone_key) >= settings.LOGIN_MAX_FAILURES_PER_PHONE
        or _failures(ip_key) >= settings.LOGIN_MAX_FAILURES_PER_IP
    ):
        raise LoginLockedError()

    user = User.objects.filter(phone=phone).first()
    if user is None:
        _DUMMY.check_password(password)
        valid = False
    else:
        valid = user.check_password(password)
    if not valid:
        _record_failure(phone_key)
        _record_failure(ip_key)
        raise InvalidCredentialsError()
    if not user.is_active:
        raise AccountDisabledError()
    cache.delete(phone_key)
    return user


# --- registration ---------------------------------------------------------------------------
@transaction.atomic
def register_customer(
    *,
    raw_phone: str,
    password: str,
    first_name: str,
    last_name: str,
    email: str,
    governorate: str,
    city: str,
    address_line: str,
    ip: str | None,
) -> User:
    phone = normalize_phone(raw_phone)
    if User.objects.filter(phone=phone).exists():
        raise PhoneInUseError()
    email = User.objects.normalize_email(email.strip()) or None
    if email and User.objects.filter(email__iexact=email).exists():
        raise EmailInUseError()
    first_name, last_name = first_name.strip(), last_name.strip()
    candidate = User(phone=phone, first_name=first_name, last_name=last_name, email=email)
    check_password_policy(password, user=candidate)
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                phone=phone,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                display_name=f"{first_name} {last_name}".strip(),
                governorate=governorate,
                city=city.strip(),
                address_line=address_line.strip(),
            )
    except IntegrityError:  # concurrent registration of the same phone/email
        raise PhoneInUseError() from None
    audit.record(actor=user, action="user.registered", entity=user, ip=ip)
    return user


# --- passwords --------------------------------------------------------------------------------
@transaction.atomic
def change_password(*, user: User, current_password: str, new_password: str, keep_session_id: str | None) -> int:
    """Change one's own password; every other session is ended. Returns how many."""
    if not user.check_password(current_password):
        raise WrongPasswordError()
    check_password_policy(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    audit.record(actor=user, action="user.password_changed", entity=user)
    return revoke_user_sessions(user, SessionRevokeReason.PASSWORD_CHANGED, except_public_id=keep_session_id)


@transaction.atomic
def admin_set_password(*, actor: User, target: User, password: str, ip: str | None) -> User:
    """Super Admin sets a new password (forgotten password, new staff). Ends all sessions."""
    check_password_policy(password, user=target)
    target.set_password(password)
    target.save(update_fields=["password"])
    revoke_user_sessions(target, SessionRevokeReason.PASSWORD_CHANGED)
    audit.record(actor=actor, action="user.password_set_by_admin", entity=target, ip=ip)
    return target


# --- default Super Admin ----------------------------------------------------------------------
DEV_DEFAULT_PASSWORD = "admin123456"  # noqa: S105 — the known dev default, refused in production


@transaction.atomic
def ensure_super_admin(*, raw_phone: str, password: str, display_name: str) -> tuple[User, bool]:
    """
    Create the default Super Admin if that phone has no account yet. An existing account keeps
    its password (so a changed password is never reset on restart) but gets the role back.
    """
    phone = normalize_phone(raw_phone)
    user = User.objects.select_for_update().filter(phone=phone).first()
    created = user is None
    if created:
        user = User.objects.create_user(phone=phone, password=password, display_name=display_name, is_staff=True)
    elif not (user.is_staff and user.is_active):
        user.is_staff = True
        user.is_active = True
        user.save(update_fields=["is_staff", "is_active"])
    super_group = Group.objects.get(name=Role.SUPER_ADMIN)
    if not user.groups.filter(pk=super_group.pk).exists():
        user.groups.add(super_group)
    if created:
        audit.record(actor=None, action="staff.default_super_admin_created", entity=user)
    return user, created

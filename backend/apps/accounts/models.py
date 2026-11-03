"""
Accounts: the phone-based user, OTP challenges and tracked sessions.

The custom user model was created in Phase 1 because AUTH_USER_MODEL cannot be swapped
after the first migration.
"""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .managers import UserManager

# E.164: "+" followed by 8–15 digits. User input is normalised by accounts.phone first.
e164_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="رقم الهاتف يجب أن يكون بالصيغة الدولية، مثل ‎+963912345678.",
    code="invalid_phone",
)


class User(AbstractBaseUser, PermissionsMixin):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    phone = models.CharField("رقم الهاتف", max_length=16, unique=True, validators=[e164_validator])
    display_name = models.CharField("الاسم", max_length=120, blank=True)
    # NULL (not "") when absent so the case-insensitive unique index ignores missing emails.
    email = models.EmailField("البريد الإلكتروني", blank=True, null=True)  # noqa: DJ001
    is_active = models.BooleanField("نشط", default=True)
    is_staff = models.BooleanField("موظف", default=False)
    date_joined = models.DateTimeField("تاريخ الانضمام", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "مستخدم"
        verbose_name_plural = "المستخدمون"
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("email"),
                name="accounts_user_email_ci_unique",
                condition=models.Q(email__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return self.display_name or self.phone

    def get_full_name(self) -> str:
        return self.display_name

    def get_short_name(self) -> str:
        return self.display_name or self.phone


class OtpChannel(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    SMS = "sms", "SMS"
    CONSOLE = "console", "Console (development)"


class OtpDeliveryStatus(models.TextChoices):
    QUEUED = "queued", "في الانتظار"
    SENT = "sent", "أُرسل"
    DELIVERED = "delivered", "سُلّم"
    FAILED = "failed", "فشل"


class OtpChallenge(models.Model):
    """One login code. Only an HMAC of the code is stored (BR-902)."""

    phone = models.CharField(max_length=16, validators=[e164_validator])
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    channel = models.CharField(max_length=16, choices=OtpChannel.choices)
    provider = models.CharField(max_length=40)
    provider_message_id = models.CharField(max_length=128, blank=True)
    delivery_status = models.CharField(
        max_length=16, choices=OtpDeliveryStatus.choices, default=OtpDeliveryStatus.QUEUED
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "-created_at"], name="otp_phone_recent_idx"),
            models.Index(fields=["request_ip", "-created_at"], name="otp_ip_recent_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(attempts__lte=20), name="otp_attempts_bounded"),
        ]

    def __str__(self) -> str:
        return f"OTP {self.phone[-3:]} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_usable(self) -> bool:
        return self.consumed_at is None and self.invalidated_at is None and self.expires_at > timezone.now()


class SessionRevokeReason(models.TextChoices):
    LOGOUT = "logout", "تسجيل خروج"
    LOGOUT_OTHERS = "logout_others", "خروج من الأجهزة الأخرى"
    REVOKED_BY_USER = "revoked_by_user", "أنهاها المستخدم"
    ADMIN = "admin", "أنهاها المدير"
    DEACTIVATED = "deactivated", "تعطيل الحساب"
    ROLE_CHANGED = "role_changed", "تغيير الصلاحيات"
    EXPIRED = "expired", "انتهت المدة"


class UserSession(models.Model):
    """
    A tracked login (BR-909). The Django session stores `public_id`; this row records the
    device and lets users and admins end sessions. The session key itself is never stored
    here — only its SHA-256 for correlation.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tracked_sessions")
    session_key_hash = models.CharField(max_length=64, unique=True)
    is_staff_session = models.BooleanField(default=False)
    user_agent_summary = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=20, choices=SessionRevokeReason.choices, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"], condition=models.Q(revoked_at__isnull=True), name="usersession_active_idx"),
        ]

    def __str__(self) -> str:
        return f"Session {self.public_id} ({self.user_id})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

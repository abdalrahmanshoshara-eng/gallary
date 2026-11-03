"""
Custom user model.

Defined in Phase 1 on purpose: Django's AUTH_USER_MODEL cannot be swapped safely after the
first migration, so the phone-based user exists before any other table references users.
OTP login, sessions management and roles are implemented in Phase 2.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .managers import UserManager

# E.164: "+" followed by 8–15 digits. Full normalisation (phonenumbers) arrives in Phase 2.
e164_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="رقم الهاتف يجب أن يكون بالصيغة الدولية، مثل ‎+963912345678.",
    code="invalid_phone",
)


class User(AbstractBaseUser, PermissionsMixin):
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

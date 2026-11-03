from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from .models import User


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, phone: str, password: str | None, **extra: Any) -> User:
        if not phone:
            raise ValueError("phone is required")
        email = extra.pop("email", None)
        user = self.model(phone=phone.strip(), email=self.normalize_email(email) or None, **extra)
        # Customers authenticate by OTP and have no usable password.
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, phone: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra)

    def create_superuser(self, phone: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("superuser must have is_staff=True and is_superuser=True")
        if not password:
            raise ValueError("superuser requires a password for the internal admin")
        return self._create_user(phone, password, **extra)

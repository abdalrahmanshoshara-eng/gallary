"""Password policy (applies to every account: customers, staff and the Super Admin)."""

from __future__ import annotations

import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers


class LetterAndDigitValidator:
    """At least one letter (Arabic or Latin) and one digit."""

    def validate(self, password: str, user=None) -> None:
        if not re.search(r"[^\W\d_]", password) or not re.search(r"\d", password):
            raise ValidationError("كلمة المرور يجب أن تحتوي على حرف ورقم على الأقل.", code="password_letter_digit")

    def get_help_text(self) -> str:
        return "يجب أن تحتوي كلمة المرور على حرف ورقم على الأقل."


def check_password_policy(password: str, user=None) -> None:
    """Raise a DRF validation error ({"password": [...]}) with Arabic messages."""
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)}) from exc

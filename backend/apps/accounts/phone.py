"""Phone number normalisation to E.164 (BR-901)."""

from __future__ import annotations

import phonenumbers
from django.conf import settings

from apps.core.errors import AppError


class InvalidPhoneError(AppError):
    code = "INVALID_PHONE"
    message = "رقم الهاتف غير صالح. أدخِل الرقم مع رمز الدولة، مثل ‎+963 9xx xxx xxx."


def normalize_phone(raw: str, region: str | None = None) -> str:
    """
    Parse user input ("0912 345 678", "+963912345678", "00963…") into E.164.

    Numbers without a country code are interpreted in PHONE_DEFAULT_REGION (Syria).
    Arabic-Indic digits are accepted.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidPhoneError()
    text = raw.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    if text.startswith("00"):
        text = "+" + text[2:]
    try:
        number = phonenumbers.parse(text, region or settings.PHONE_DEFAULT_REGION)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneError() from exc
    if not phonenumbers.is_valid_number(number):
        raise InvalidPhoneError()
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def mask_phone(phone: str) -> str:
    return f"{phone[:4]}•••{phone[-3:]}" if len(phone) > 7 else "•••"

"""
OTP code generation, hashing and short-lived transit encryption.

- Stored: HMAC-SHA256 of "phone:code" keyed from SECRET_KEY (BR-902), compared in constant
  time. Binding the phone prevents reusing a hash for another number.
- In transit to the Celery task: Fernet-encrypted with a 5-minute TTL so the code never
  sits in plaintext in the broker, task arguments or logs.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils.crypto import constant_time_compare, salted_hmac

_HASH_SALT = "apps.accounts.otp.hash"
_TRANSIT_SALT = b"apps.accounts.otp.transit:"


def generate_code(length: int | None = None) -> str:
    length = length or settings.OTP_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_code(phone: str, code: str) -> str:
    return salted_hmac(_HASH_SALT, f"{phone}:{code}", algorithm="sha256").hexdigest()


def code_matches(phone: str, code: str, code_hash: str) -> bool:
    return constant_time_compare(hash_code(phone, code), code_hash)


def _fernet() -> Fernet:
    digest = hashlib.sha256(_TRANSIT_SALT + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(code: str) -> str:
    return _fernet().encrypt(code.encode()).decode()


class SealExpiredError(Exception):
    pass


def unseal(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode(), ttl=settings.OTP_TTL_SECONDS).decode()
    except InvalidToken as exc:
        raise SealExpiredError from exc

"""
Logging helpers: request-id injection and redaction of sensitive values.

Redaction is defence in depth — code must never log OTP codes, session ids or tokens in
the first place. The filter also masks phone numbers to their last 3 digits.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pythonjsonlogger.json import JsonFormatter as _BaseJsonFormatter

from .request_context import get_request_id

REDACTED = "[REDACTED]"

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "otp",
        "code",
        "token",
        "secret",
        "authorization",
        "cookie",
        "set-cookie",
        "sessionid",
        "session_key",
        "csrftoken",
        "x-csrftoken",
        "api_key",
    }
)

# Standalone phone-like numbers only: not part of UUIDs, decimals, timestamps or identifiers.
_PHONE_RE = re.compile(r"(?<![\w.:/-])\+?\d{9,15}(?![\w.:/-])")
_SECRET_PAIR_RE = re.compile(
    r"(?i)\b(password|otp|code|token|secret|sessionid|csrftoken|authorization)\b(\s*[=:]\s*)([^\s,;&]+)"
)


def mask_phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"***{digits[-3:]}" if len(digits) >= 3 else REDACTED


def redact_text(text: str) -> str:
    text = _SECRET_PAIR_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    return _PHONE_RE.sub(mask_phone, text)


def redact_value(key: str, value: Any) -> Any:
    if key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {k: redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, str):
        return redact_text(value)
    return value


# Attributes present on every LogRecord; anything else was passed via `extra=`.
_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "request_id",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id() or "-"
        return True


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_value(str(k), v) for k, v in record.args.items()}
            else:
                record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args)
        for key, value in list(vars(record).items()):
            if key not in _STANDARD_ATTRS:
                setattr(record, key, redact_value(key, value))
        return True


class JsonFormatter(_BaseJsonFormatter):
    """JSON log lines with stable field names."""

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = log_record.pop("levelname", record.levelname)
        log_record["logger"] = log_record.pop("name", record.name)
        log_record.setdefault("request_id", getattr(record, "request_id", "-"))

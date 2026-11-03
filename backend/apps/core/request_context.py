"""Request-scoped context (request id) shared by HTTP, WebSocket and Celery code paths."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Accept only safe, bounded ids coming from upstream proxies.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def new_request_id() -> str:
    return uuid.uuid4().hex


def sanitize_request_id(value: str | None) -> str:
    if value and _VALID_REQUEST_ID.match(value):
        return value
    return new_request_id()


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str | None):
    """Set the current request id; returns a token for `reset_request_id`."""
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)

"""HTTP helpers shared by services that need request metadata."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str | None:
    """
    The client's IP address, trusting exactly NUM_PROXIES reverse proxies (nginx = 1).

    Mirrors DRF's throttling identification so limits and logs agree. The left-most
    X-Forwarded-For entries can be forged by the client, so only the entry appended by our
    own proxy is used.
    """
    num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    remote_addr = request.META.get("REMOTE_ADDR")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if num_proxies and forwarded:
        addrs = [a.strip() for a in forwarded.split(",") if a.strip()]
        if addrs:
            return addrs[-min(num_proxies, len(addrs))]
    return remote_addr


def user_agent_summary(request: HttpRequest, limit: int = 200) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:limit]

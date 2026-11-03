"""
Tracked sessions (BR-908…910).

Revocation is enforced on the next request: the revoked id is cached for an immediate
effect and re-checked against the database at least every SESSION_TOUCH_INTERVAL_SECONDS,
so losing the cache can delay — but never skip — a revocation.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.core.events import publish_on_commit
from apps.core.http import client_ip, user_agent_summary

from ..events import SessionRevoked
from ..models import User, UserSession

SESSION_ID_KEY = "_us"
AUTH_AT_KEY = "_auth_at"
SEEN_AT_KEY = "_seen_at"
TOUCHED_AT_KEY = "_touched_at"
STAFF_KEY = "_staff"


def revoked_cache_key(public_id: str) -> str:
    return f"accounts:session-revoked:{public_id}"


def _hash_key(session_key: str) -> str:
    return hashlib.sha256(session_key.encode()).hexdigest()


def lifetime_for(user: User) -> int:
    return settings.STAFF_SESSION_ABSOLUTE_SECONDS if user.is_staff else settings.CUSTOMER_SESSION_SECONDS


def start_session(request: HttpRequest, user: User) -> UserSession:
    """Called on every login (OTP or internal admin) via the user_logged_in signal."""
    session = request.session
    if session.session_key is None:
        session.save()
    lifetime = lifetime_for(user)
    now = timezone.now()
    tracked = UserSession.objects.create(
        user=user,
        session_key_hash=_hash_key(session.session_key),
        is_staff_session=user.is_staff,
        user_agent_summary=user_agent_summary(request),
        ip=client_ip(request),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=lifetime),
    )
    ts = now.timestamp()
    session[SESSION_ID_KEY] = str(tracked.public_id)
    session[AUTH_AT_KEY] = ts
    session[SEEN_AT_KEY] = ts
    session[TOUCHED_AT_KEY] = ts
    session[STAFF_KEY] = user.is_staff
    session.set_expiry(lifetime)
    return tracked


def _revoke(queryset, reason: str) -> list[UserSession]:
    now = timezone.now()
    sessions = list(queryset.filter(revoked_at__isnull=True).select_for_update())
    if not sessions:
        return []
    UserSession.objects.filter(pk__in=[s.pk for s in sessions]).update(revoked_at=now, revoked_reason=reason)
    for s in sessions:
        cache.set(revoked_cache_key(str(s.public_id)), True, timeout=settings.CUSTOMER_SESSION_SECONDS)
        publish_on_commit(SessionRevoked(session_public_id=s.public_id, user_id=s.user_id, reason=reason))
    return sessions


@transaction.atomic
def revoke_session(session: UserSession, reason: str) -> bool:
    return bool(_revoke(UserSession.objects.filter(pk=session.pk), reason))


@transaction.atomic
def revoke_user_sessions(user: User, reason: str, *, except_public_id: str | None = None) -> int:
    qs = UserSession.objects.filter(user=user)
    if except_public_id:
        qs = qs.exclude(public_id=except_public_id)
    return len(_revoke(qs, reason))


def current_session_id(request: HttpRequest) -> str | None:
    return request.session.get(SESSION_ID_KEY)


def is_revoked_in_cache(public_id: str) -> bool:
    try:
        return bool(cache.get(revoked_cache_key(public_id)))
    except Exception:  # noqa: BLE001 — cache outage falls back to the periodic DB check
        return False


def touch(public_id: str, *, extend_to=None) -> bool:
    """Record activity; returns False when the session is revoked, expired or unknown."""
    now = timezone.now()
    updates = {"last_seen_at": now}
    if extend_to is not None:
        updates["expires_at"] = extend_to
    return bool(
        UserSession.objects.filter(public_id=public_id, revoked_at__isnull=True, expires_at__gt=now).update(**updates)
    )


def session_is_active(public_id: str, user_id: int) -> bool:
    """Used by WebSocket consumers at connect time."""
    if is_revoked_in_cache(public_id):
        return False
    return UserSession.objects.filter(
        public_id=public_id,
        user_id=user_id,
        user__is_active=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists()

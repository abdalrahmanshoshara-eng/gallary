"""
Enforces the session policy on every authenticated request (BR-908, BR-909):

- revoked sessions are logged out (cache check every request, DB re-check periodically);
- staff sessions end after 30 minutes idle or 12 hours absolute;
- customer sessions slide: the 30-day expiry is renewed once half of it has elapsed.

Writes are throttled: the session and its UserSession row are updated at most once per
minute / per SESSION_TOUCH_INTERVAL_SECONDS respectively.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .models import SessionRevokeReason, UserSession
from .services import sessions as svc

SEEN_WRITE_INTERVAL = 60


class SessionPolicyMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            self._enforce(request)
        return self.get_response(request)

    def _end(self, request: HttpRequest, public_id: str | None, reason: str | None = None) -> None:
        if public_id and reason:
            tracked = UserSession.objects.filter(public_id=public_id).first()
            if tracked:
                svc.revoke_session(tracked, reason)
        logout(request)

    def _enforce(self, request: HttpRequest) -> None:
        session = request.session
        public_id = session.get(svc.SESSION_ID_KEY)
        if not public_id:
            # Authenticated session without tracking (created before Phase 2): end it.
            logout(request)
            return
        if svc.is_revoked_in_cache(public_id):
            logout(request)
            return

        now = timezone.now().timestamp()
        auth_at = float(session.get(svc.AUTH_AT_KEY, now))
        seen_at = float(session.get(svc.SEEN_AT_KEY, now))
        touched_at = float(session.get(svc.TOUCHED_AT_KEY, 0))
        is_staff = bool(session.get(svc.STAFF_KEY))

        if is_staff != request.user.is_staff:
            # Privileges changed since login: require a fresh login under the right policy.
            self._end(request, public_id, SessionRevokeReason.ROLE_CHANGED)
            return

        idle_expired = now - seen_at > settings.STAFF_SESSION_IDLE_SECONDS
        absolute_expired = now - auth_at > settings.STAFF_SESSION_ABSOLUTE_SECONDS
        if is_staff and (idle_expired or absolute_expired):
            self._end(request, public_id, SessionRevokeReason.EXPIRED)
            return

        extend_to = None
        if (
            not is_staff
            and now - auth_at > settings.CUSTOMER_SESSION_SECONDS / 2
            and (now - float(session.get("_renewed_at", auth_at)) > settings.CUSTOMER_SESSION_SECONDS / 2)
        ):
            session.set_expiry(settings.CUSTOMER_SESSION_SECONDS)
            session["_renewed_at"] = now
            extend_to = timezone.now() + timedelta(seconds=settings.CUSTOMER_SESSION_SECONDS)

        if now - touched_at > settings.SESSION_TOUCH_INTERVAL_SECONDS or extend_to is not None:
            if not svc.touch(public_id, extend_to=extend_to):
                logout(request)
                return
            session[svc.TOUCHED_AT_KEY] = now

        if now - seen_at > SEEN_WRITE_INTERVAL:
            session[svc.SEEN_AT_KEY] = now

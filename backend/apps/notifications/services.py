"""Creating notifications and their read state. Call `notify` inside the event's transaction."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.events import publish_on_commit

from . import catalog
from .channels import email_enabled
from .events import NotificationCreated
from .models import EmailStatus, Notification, NotificationPreference

logger = logging.getLogger(__name__)
MAX_EMAIL_ATTEMPTS = 3


def preference(user) -> NotificationPreference:
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return pref


def _wants_email(user) -> bool:
    if not (email_enabled() and user.email and user.is_active):
        return False
    pref = NotificationPreference.objects.filter(user=user).only("email_enabled").first()
    return pref is None or pref.email_enabled


def notify(
    user, kind: str, *, params: dict[str, Any] | None = None, link: str = "", dedupe_key: str = ""
) -> Notification | None:
    """
    Record one notification for `user` (a User or its id). Returns None when `dedupe_key` was
    already used for this user. The bell update and the e-mail run after commit, so a rolled-back
    event never notifies anyone and a mail failure never breaks the event.
    """
    if not isinstance(user, get_user_model()):
        user = get_user_model().objects.get(pk=user)
    spec = catalog.KINDS[kind]
    params = params or {}
    title, body = spec.render(params)
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                user=user,
                kind=kind,
                category=spec.category,
                title=title,
                body=body,
                link=link,
                data={k: v for k, v in params.items() if isinstance(v, str | int | float | bool)},
                dedupe_key=dedupe_key,
                email_status=EmailStatus.PENDING if spec.email and _wants_email(user) else EmailStatus.NONE,
            )
    except IntegrityError:
        if dedupe_key:
            return None
        raise
    publish_on_commit(
        NotificationCreated(
            user_id=user.pk, notification_id=str(notification.public_id), kind=kind, title=title, link=link
        )
    )
    if notification.email_status == EmailStatus.PENDING:
        transaction.on_commit(lambda: _queue_email(notification.pk))
    return notification


def _queue_email(notification_id: int) -> None:
    from .tasks import send_notification_email

    try:
        send_notification_email.delay(notification_id)
    except Exception:  # broker down: the outbox sweep retries it
        logger.exception("notification_email_queue_failed", extra={"notification": notification_id})


def mark_read(user, notification: Notification) -> Notification:
    if notification.user_id != user.pk:
        raise Notification.DoesNotExist
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_read(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=timezone.now())


def set_email_enabled(user, enabled: bool) -> NotificationPreference:
    pref = preference(user)
    pref.email_enabled = enabled
    pref.save(update_fields=["email_enabled", "updated_at"])
    return pref


def sweep(now=None) -> dict[str, int]:
    """Daily housekeeping: drop old read notifications; re-queue mail stuck in the outbox."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=settings.NOTIFICATIONS_RETENTION_DAYS)
    deleted, _ = Notification.objects.filter(read_at__isnull=False, created_at__lt=cutoff).delete()
    stale = Notification.objects.filter(
        email_status__in=[EmailStatus.PENDING, EmailStatus.SENDING],
        email_attempts__lt=MAX_EMAIL_ATTEMPTS,
        created_at__lt=now - timedelta(minutes=10),
        created_at__gte=now - timedelta(days=2),
    )
    ids = list(stale.values_list("pk", flat=True))
    Notification.objects.filter(pk__in=ids).update(email_status=EmailStatus.PENDING)
    for pk in ids:
        _queue_email(pk)
    return {"deleted": deleted, "requeued": len(ids)}

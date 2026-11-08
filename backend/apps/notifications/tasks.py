"""Background e-mail delivery for notifications (default queue)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from . import services
from .channels import EmailDeliveryError, compose, get_email_sender
from .models import EmailStatus, Notification

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.notifications.tasks.send_notification_email",
    queue="notifications",
    bind=True,
    max_retries=services.MAX_EMAIL_ATTEMPTS - 1,
    acks_late=True,
    ignore_result=True,
)
def send_notification_email(self, notification_id: int) -> None:
    # Claim the row so a redelivered task never sends the same mail twice.
    claimed = Notification.objects.filter(pk=notification_id, email_status=EmailStatus.PENDING).update(
        email_status=EmailStatus.SENDING
    )
    if not claimed:
        return
    notification = Notification.objects.select_related("user").get(pk=notification_id)
    to = notification.user.email
    if not to:
        Notification.objects.filter(pk=notification_id).update(email_status=EmailStatus.NONE)
        return
    attempts = notification.email_attempts + 1
    try:
        get_email_sender().send(compose(notification, to))
    except EmailDeliveryError as exc:
        error = str(exc)[:300]
        final = attempts >= services.MAX_EMAIL_ATTEMPTS
        Notification.objects.filter(pk=notification_id).update(
            email_status=EmailStatus.FAILED if final else EmailStatus.PENDING,
            email_attempts=attempts,
            email_error=error,
        )
        logger.warning("notification_email_failed", extra={"notification": notification_id, "attempt": attempts})
        if not final:
            raise self.retry(exc=exc, countdown=60 * 2 ** (attempts - 1)) from exc
        return
    Notification.objects.filter(pk=notification_id).update(
        email_status=EmailStatus.SENT, email_attempts=attempts, email_sent_at=timezone.now(), email_error=""
    )


@shared_task(name="apps.notifications.tasks.sweep", queue="default", ignore_result=True)
def sweep() -> dict[str, int]:
    return services.sweep()

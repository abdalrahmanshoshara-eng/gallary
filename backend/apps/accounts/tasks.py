"""Background delivery of OTP codes (critical queue)."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import OtpChallenge, OtpDeliveryStatus
from .otp.crypto import SealExpiredError, unseal
from .otp.senders import OtpDeliveryError, get_otp_sender

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.accounts.tasks.deliver_otp",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
    ignore_result=True,
)
def deliver_otp(self, challenge_id: int, sealed_code: str) -> None:
    challenge = OtpChallenge.objects.filter(pk=challenge_id).first()
    if challenge is None or not challenge.is_usable:
        return
    try:
        code = unseal(sealed_code)
    except SealExpiredError:
        OtpChallenge.objects.filter(pk=challenge_id).update(delivery_status=OtpDeliveryStatus.FAILED)
        logger.warning("otp_seal_expired", extra={"challenge": challenge_id})
        return

    try:
        result = get_otp_sender().send(challenge.phone, code)
    except OtpDeliveryError as exc:
        if self.request.retries < self.max_retries and challenge.expires_at > timezone.now():
            raise self.retry(exc=exc) from exc
        OtpChallenge.objects.filter(pk=challenge_id).update(delivery_status=OtpDeliveryStatus.FAILED)
        logger.error("otp_delivery_failed", extra={"challenge": challenge_id, "provider": challenge.provider})
        return

    OtpChallenge.objects.filter(pk=challenge_id).update(
        delivery_status=OtpDeliveryStatus.SENT, provider_message_id=result.provider_message_id
    )

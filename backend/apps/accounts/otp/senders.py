"""
OTP delivery channels behind one interface (ADR-16).

Adding the WhatsApp provider later = a new `OtpSender` subclass registered in
settings.OTP_SENDERS and selected with OTP_SENDER — no change to authentication logic.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string

from ..models import OtpChannel


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str = ""


class OtpDeliveryError(Exception):
    """Transient delivery failure; the task may retry."""


class OtpSender:
    name: str = "base"
    channel: str = OtpChannel.WHATSAPP
    #: False when logins cannot be served (no provider configured yet).
    available: bool = True

    def send(self, phone: str, code: str) -> SendResult:
        raise NotImplementedError


class DisabledSender(OtpSender):
    """Used until the WhatsApp service is subscribed (BR-901c). Requests get 503."""

    name = "disabled"
    available = False

    def send(self, phone: str, code: str) -> SendResult:
        raise OtpDeliveryError("OTP delivery is disabled")


class ConsoleSender(OtpSender):
    """
    Development only: writes the code to this process's stdout. It deliberately bypasses
    logging so codes never reach log pipelines. Production settings refuse this sender.
    """

    name = "console"
    channel = OtpChannel.CONSOLE

    def send(self, phone: str, code: str) -> SendResult:
        sys.stdout.write(f"\n[DEV OTP] phone=…{phone[-4:]} code={code}\n")
        sys.stdout.flush()
        return SendResult(provider_message_id="console")


@lru_cache(maxsize=1)
def get_otp_sender() -> OtpSender:
    path = settings.OTP_SENDERS.get(settings.OTP_SENDER)
    if path is None:
        raise ValueError(f"Unknown OTP_SENDER {settings.OTP_SENDER!r}")
    return import_string(path)()

"""
E-mail delivery behind one interface (ADR-16 style, like the OTP senders).

The default sender uses Django's mail framework, so SMTP is configured with the standard
EMAIL_* settings. Another provider (an HTTP API, SMS or WhatsApp later) is a new sender class
selected with NOTIFICATIONS_EMAIL_SENDER — no change to the events that create notifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape, linebreaks
from django.utils.module_loading import import_string

from .models import Notification

BRAND = "منصة الفن الدمشقية"


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


class EmailDeliveryError(Exception):
    """Transient failure; the task retries."""


class EmailSender:
    name = "base"

    def send(self, message: OutgoingEmail) -> None:
        raise NotImplementedError


class DjangoEmailSender(EmailSender):
    """SMTP (or any EMAIL_BACKEND) through django.core.mail."""

    name = "django"

    def send(self, message: OutgoingEmail) -> None:
        mail = EmailMultiAlternatives(
            subject=message.subject, body=message.text, from_email=settings.DEFAULT_FROM_EMAIL, to=[message.to]
        )
        mail.attach_alternative(message.html, "text/html")
        try:
            mail.send(fail_silently=False)
        except Exception as exc:  # smtplib / socket errors → retry
            raise EmailDeliveryError(str(exc)) from exc


@lru_cache(maxsize=1)
def get_email_sender() -> EmailSender:
    return import_string(settings.NOTIFICATIONS_EMAIL_SENDER)()


def email_enabled() -> bool:
    return bool(settings.NOTIFICATIONS_EMAIL_ENABLED)


def absolute(path: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{path}" if path.startswith("/") else path


def compose(notification: Notification, to: str) -> OutgoingEmail:
    """Plain text + a minimal RTL HTML version (no remote images, no tracking)."""
    link = absolute(notification.link) if notification.link else ""
    settings_link = absolute("/notifications")
    footer = f"تصلك هذه الرسالة لأن لديك حساباً في {BRAND}. لإيقاف رسائل البريد: {settings_link}"
    text_parts = [notification.title, "", notification.body]
    if link:
        text_parts += ["", f"افتح في المنصة: {link}"]
    text_parts += ["", "—", footer]

    button = (
        f'<p style="margin:24px 0"><a href="{escape(link)}" style="background:#6b3a2a;color:#fff;'
        f'padding:12px 20px;border-radius:6px;text-decoration:none">افتح في المنصة</a></p>'
        if link
        else ""
    )
    html = (
        '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"></head>'
        '<body style="margin:0;background:#f5f0e8;font-family:Tahoma,Arial,sans-serif;color:#2b2420">'
        '<div style="max-width:560px;margin:0 auto;padding:32px 24px;text-align:right">'
        f'<p style="color:#6b3a2a;font-size:18px;font-weight:bold;margin:0 0 24px">{escape(BRAND)}</p>'
        f'<h1 style="font-size:20px;color:#6b3a2a;margin:0 0 12px">{escape(notification.title)}</h1>'
        f'<div style="font-size:15px;line-height:1.8">{linebreaks(escape(notification.body))}</div>'
        f"{button}"
        '<hr style="border:none;border-top:1px solid #d9cfc2;margin:32px 0 16px">'
        f'<p style="font-size:12px;color:#7a6e64">{escape(footer)}</p>'
        "</div></body></html>"
    )
    return OutgoingEmail(to=to, subject=f"{notification.title} — {BRAND}", text="\n".join(text_parts), html=html)

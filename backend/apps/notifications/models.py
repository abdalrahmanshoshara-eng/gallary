"""In-app notifications and their e-mail delivery state (PRD F-NTF-01/02, §26)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.TextChoices):
    ORDER = "order", "الطلبات"
    AUCTION = "auction", "المزادات"
    REQUEST = "request", "طلبات المزاد"
    PAYOUT = "payout", "المستحقات"


class EmailStatus(models.TextChoices):
    NONE = "none", "لا يُرسل"
    PENDING = "pending", "بانتظار الإرسال"
    SENDING = "sending", "قيد الإرسال"
    SENT = "sent", "أُرسل"
    FAILED = "failed", "فشل"


class Notification(models.Model):
    """One message for one user. Text is a snapshot taken when the event happened."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=48)
    category = models.CharField(max_length=12, choices=Category.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict, blank=True)
    #: Non-empty keys are unique per user: reminders and "ending soon" are sent once.
    dedupe_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    email_status = models.CharField(max_length=8, choices=EmailStatus.choices, default=EmailStatus.NONE)
    email_attempts = models.PositiveSmallIntegerField(default=0)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="notif_user_recent"),
            models.Index(fields=["user"], condition=models.Q(read_at__isnull=True), name="notif_user_unread"),
            models.Index(
                fields=["email_status", "created_at"],
                condition=models.Q(email_status__in=["pending", "sending"]),
                name="notif_email_outbox",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedupe_key"], condition=~models.Q(dedupe_key=""), name="notif_user_dedupe_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} → {self.user_id}"


class NotificationPreference(models.Model):
    """Per-user channel choices. In-app notifications are always kept."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="notification_preference"
    )
    email_enabled = models.BooleanField("نسخة بالبريد للأحداث المهمة", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"preferences of {self.user_id}"

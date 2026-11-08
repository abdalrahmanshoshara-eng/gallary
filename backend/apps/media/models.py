"""
Images stored in object storage (BR-108, ADR-17).

The uploaded original goes to the PRIVATE bucket (it may contain EXIF/GPS metadata).
Public WebP variants without metadata are generated asynchronously into the PUBLIC
bucket. Only keys are stored, never URLs.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ImagePurpose(models.TextChoices):
    ARTWORK = "artwork", "صورة عمل فني"
    ARTIST = "artist", "صورة فنان"
    AUCTION_REQUEST = "auction_request", "صورة طلب مزاد"
    BANNER = "banner", "صورة بنر"


class ImageStatus(models.TextChoices):
    PENDING = "pending", "قيد المعالجة"
    READY = "ready", "جاهزة"
    FAILED = "failed", "فشلت المعالجة"


class ImageAsset(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField(max_length=20, choices=ImagePurpose.choices)
    original_key = models.CharField(max_length=300)
    original_content_type = models.CharField(max_length=50)
    original_bytes = models.PositiveIntegerField()
    width = models.PositiveIntegerField(help_text="بعد تصحيح الاتجاه")
    height = models.PositiveIntegerField()
    #: {"400": {"key": "...", "width": 400, "height": 300}, ...}
    variants = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=ImageStatus.choices, default=ImageStatus.PENDING)
    error = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.purpose}:{self.public_id} ({self.status})"

    @property
    def is_ready(self) -> bool:
        return self.status == ImageStatus.READY

    def variant_keys(self) -> list[str]:
        return [v["key"] for v in self.variants.values()]

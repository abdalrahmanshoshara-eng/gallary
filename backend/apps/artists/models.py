"""
Artists (PRD F-CAT-02). Managed by staff only — artists have no account in the MVP.
Contact details and internal notes are never exposed by public endpoints.
Commission agreements (ArtistAgreement, BR-701) set the artist's platform share.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ArtistStatus(models.TextChoices):
    ACTIVE = "active", "ظاهر"
    HIDDEN = "hidden", "مخفي"


class Artist(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField("الاسم", max_length=200)
    slug = models.SlugField("المعرّف", max_length=220, unique=True, allow_unicode=True)
    biography = models.TextField("النبذة", blank=True)
    city = models.CharField("المدينة", max_length=100, blank=True)
    birth_year = models.PositiveSmallIntegerField("سنة الميلاد", null=True, blank=True)
    photo = models.OneToOneField("media.ImageAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=ArtistStatus.choices, default=ArtistStatus.ACTIVE)
    is_featured = models.BooleanField("مميّز", default=False)

    # Internal only (never in public serializers).
    contact_phone = models.CharField("هاتف التواصل", max_length=32, blank=True)
    contact_email = models.EmailField("بريد التواصل", blank=True)
    internal_notes = models.TextField("ملاحظات داخلية", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "فنان"
        verbose_name_plural = "الفنانون"
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "is_featured"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(birth_year__isnull=True) | models.Q(birth_year__gte=1800, birth_year__lte=2100),
                name="artist_birth_year_range",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class AgreementStatus(models.TextChoices):
    ACTIVE = "active", "نشطة"
    ENDED = "ended", "منتهية"


class ArtistAgreement(models.Model):
    """The platform's commission for an artist's works (BR-701, second in the order of
    precedence). One active agreement per artist; a new one ends the previous. Changes apply
    to new orders only: orders keep their snapshot (BR-703)."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="agreements")
    commission_rate = models.DecimalField("نسبة العمولة %", max_digits=5, decimal_places=2)
    status = models.CharField(max_length=8, choices=AgreementStatus.choices, default=AgreementStatus.ACTIVE)
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "اتفاقية عمولة"
        verbose_name_plural = "اتفاقيات العمولة"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["artist"], condition=models.Q(status="active"), name="artist_one_active_agreement"
            ),
            models.CheckConstraint(
                condition=models.Q(commission_rate__gte=0, commission_rate__lte=100), name="agreement_rate_range"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")),
                name="agreement_dates_ordered",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.artist_id}: {self.commission_rate}% ({self.status})"

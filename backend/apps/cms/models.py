"""
Site content (F-CMS): versioned static pages, FAQ, home banners and curated artworks.

Pages are edited as a draft and published as immutable versions; the deposit policy's
published version is what customers accept at checkout (BR-313). Bodies are a limited
Markdown rendered by the frontend into elements — raw HTML is never rendered.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class PageSlug(models.TextChoices):
    ABOUT = "about", "من نحن"
    TERMS = "terms", "شروط الاستخدام"
    PRIVACY = "privacy", "سياسة الخصوصية"
    DEPOSIT_POLICY = "deposit-policy", "سياسة العربون والإلغاء"


class Page(models.Model):
    slug = models.CharField(max_length=20, choices=PageSlug.choices, unique=True)
    draft_title = models.CharField(max_length=200, blank=True)
    draft_body = models.TextField(blank=True)
    draft_updated_at = models.DateTimeField(null=True, blank=True)
    draft_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    published = models.ForeignKey("PageVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "صفحة"
        verbose_name_plural = "الصفحات"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.slug


class PageVersion(models.Model):
    """Immutable once created (a published text that customers may have accepted)."""

    page = models.ForeignKey(Page, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    code = models.CharField(max_length=20)  # e.g. 2026-11-08 / 2026-11-08-2 (stored on orders)
    title = models.CharField(max_length=200)
    body = models.TextField()
    published_at = models.DateTimeField(default=timezone.now)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["page", "number"], name="page_version_number_unique"),
            models.UniqueConstraint(fields=["page", "code"], name="page_version_code_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.page_id} v{self.number} ({self.code})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("Published page versions are immutable")
        super().save(*args, **kwargs)


class FaqItem(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    question = models.CharField(max_length=300)
    answer = models.TextField()
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سؤال شائع"
        verbose_name_plural = "الأسئلة الشائعة"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.question


class Banner(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.OneToOneField("media.ImageAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    link_url = models.CharField(max_length=500, blank=True)
    link_label = models.CharField(max_length=60, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "بنر"
        verbose_name_plural = "البنرات"
        ordering = ["sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(starts_at__isnull=True) | Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="banner_window_ordered",
            ),
            models.CheckConstraint(condition=Q(link_url="") | ~Q(link_label=""), name="banner_link_has_label"),
        ]

    def __str__(self) -> str:
        return self.title


class FeaturedArtwork(models.Model):
    artwork = models.OneToOneField("artworks.Artwork", on_delete=models.CASCADE, related_name="featured")
    sort_order = models.PositiveIntegerField(default=0)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "عمل مختار"
        verbose_name_plural = "الأعمال المختارة"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.artwork_id} #{self.sort_order}"

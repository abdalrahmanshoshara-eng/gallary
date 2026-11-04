"""
The artwork itself (PMP §11). Commercial offers (price, stock) live in Listing (Phase 4),
so an artwork survives sales, auctions and re-offers. Artworks are never deleted once
published; they are hidden or archived (BR-101, BR-802).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils import timezone


class PublicationStatus(models.TextChoices):
    DRAFT = "draft", "مسودة"
    PUBLISHED = "published", "منشور"
    HIDDEN = "hidden", "مخفي"


class ArchiveVisibility(models.TextChoices):
    VISIBLE = "visible", "ظاهر في الأرشيف"
    HIDDEN = "hidden", "مخفي من الأرشيف"


class Artwork(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField("العنوان", max_length=250)
    slug = models.SlugField("المعرّف", max_length=270, unique=True, allow_unicode=True)
    description = models.TextField("الوصف", blank=True)

    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="artworks")
    artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="artworks",
        verbose_name="الفنان",
    )
    creator_name_override = models.CharField("اسم المُبدع (إن لم يكن الفنان مسجلاً)", max_length=200, blank=True)
    executor = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="executed_artworks",
        verbose_name="المنفذ",
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_artworks",
        help_text="المالك عندما يكون عميلاً (أعمال طلبات المزاد)",
    )
    owner_name = models.CharField("المالك / صاحب حق البيع", max_length=200, blank=True)
    rights_holder = models.CharField("صاحب الحقوق", max_length=200, blank=True)

    materials = models.ManyToManyField("catalog.Material", blank=True, related_name="artworks")
    techniques = models.ManyToManyField("catalog.Technique", blank=True, related_name="artworks")
    tags = models.ManyToManyField("catalog.Tag", blank=True, related_name="artworks")

    height_cm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    width_cm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    depth_cm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    year_created = models.PositiveSmallIntegerField("سنة الإنشاء", null=True, blank=True)

    publication_status = models.CharField(
        max_length=10, choices=PublicationStatus.choices, default=PublicationStatus.DRAFT
    )
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archive_visibility = models.CharField(
        max_length=10, choices=ArchiveVisibility.choices, default=ArchiveVisibility.VISIBLE
    )
    internal_notes = models.TextField("ملاحظات داخلية", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Normalised search key (title, creator, description, category, materials, techniques,
    # tags) maintained by services.refresh_search_text — never displayed (§21).
    search_text = models.TextField(blank=True, default="", editable=False)

    class Meta:
        verbose_name = "عمل فني"
        verbose_name_plural = "الأعمال الفنية"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["publication_status", "-published_at"], name="artwork_public_listing_idx"),
            models.Index(fields=["archived_at"], name="artwork_archived_idx"),
            # Trigram GIN index: serves `search_text LIKE '%term%'` for every query word.
            GinIndex(fields=["search_text"], opclasses=["gin_trgm_ops"], name="artwork_search_trgm"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(artist__isnull=False) | ~models.Q(creator_name_override=""),
                name="artwork_has_creator",
            ),
            models.CheckConstraint(
                condition=models.Q(year_created__isnull=True)
                | models.Q(year_created__gte=1000, year_created__lte=2100),
                name="artwork_year_range",
            ),
            *[
                models.CheckConstraint(
                    condition=models.Q(**{f"{f}__isnull": True}) | models.Q(**{f"{f}__gt": 0}),
                    name=f"artwork_{f}_positive",
                )
                for f in ("height_cm", "width_cm", "depth_cm", "weight_kg")
            ],
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def creator_display(self) -> str:
        return self.artist.name if self.artist_id else self.creator_name_override

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class ArtworkImage(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    artwork = models.ForeignKey(Artwork, on_delete=models.CASCADE, related_name="images")
    asset = models.OneToOneField("media.ImageAsset", on_delete=models.PROTECT, related_name="artwork_image")
    alt_text = models.CharField("وصف الصورة", max_length=250, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["artwork"], condition=models.Q(is_primary=True), name="artwork_single_primary_image"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.artwork_id}#{self.sort_order}"

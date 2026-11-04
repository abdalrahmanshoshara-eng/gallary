"""
Listing: the commercial offer for an artwork (BR-101, BR-201…213).

The artwork carries the artistic identity; a listing carries price, stock and commission.
Inventory invariants are enforced by CHECK constraints, and every stock change goes through
`services` under `SELECT … FOR UPDATE` (BR-206), so overselling is impossible even under
concurrency.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.artworks.models import Artwork
from apps.core.models import DepositType


class SaleMode(models.TextChoices):
    FIXED_PRICE = "fixed_price", "سعر ثابت"
    AUCTION = "auction", "مزاد"


class QuantityMode(models.TextChoices):
    UNIQUE = "unique", "قطعة فريدة"
    LIMITED = "limited", "كمية محدودة"
    UNLIMITED = "unlimited", "غير محدودة"


class ListingStatus(models.TextChoices):
    DRAFT = "draft", "مسودة"
    ACTIVE = "active", "نشط"
    SOLD_OUT = "sold_out", "نفدت الكمية"
    ENDED = "ended", "انتهى"
    WITHDRAWN = "withdrawn", "سُحب"


class Listing(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    artwork = models.ForeignKey(Artwork, on_delete=models.PROTECT, related_name="listings")
    sale_mode = models.CharField(max_length=12, choices=SaleMode.choices, default=SaleMode.FIXED_PRICE)
    status = models.CharField(max_length=10, choices=ListingStatus.choices, default=ListingStatus.DRAFT)

    # Pricing — set by the Super Admin only (BR-212).
    price_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    commission_rate_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    deposit_type = models.CharField(max_length=12, choices=DepositType.choices, blank=True)
    deposit_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pricing_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pricing_approved_at = models.DateTimeField(null=True, blank=True)

    # Stock (BR-203…207). quantity_total is NULL for UNLIMITED.
    quantity_mode = models.CharField(max_length=10, choices=QuantityMode.choices, default=QuantityMode.UNIQUE)
    quantity_total = models.PositiveIntegerField(null=True, blank=True)
    quantity_available = models.IntegerField(default=1)
    quantity_reserved = models.IntegerField(default=0)
    quantity_sold = models.IntegerField(default=0)
    max_per_order = models.PositiveSmallIntegerField(default=1)

    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "عرض"
        verbose_name_plural = "العروض"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "sale_mode"], name="listing_status_mode_idx"),
            models.Index(fields=["price_usd"], name="listing_price_idx"),
        ]
        constraints = [
            # BR-202: one active offer per artwork.
            models.UniqueConstraint(
                fields=["artwork"], condition=Q(status="active"), name="listing_one_active_per_artwork"
            ),
            models.CheckConstraint(
                condition=Q(quantity_available__gte=0, quantity_reserved__gte=0, quantity_sold__gte=0),
                name="listing_quantities_non_negative",
            ),
            models.CheckConstraint(
                condition=~Q(quantity_mode="unique") | Q(quantity_total=1), name="listing_unique_has_one"
            ),
            models.CheckConstraint(
                condition=~Q(quantity_mode="limited") | Q(quantity_total__gt=1), name="listing_limited_more_than_one"
            ),
            models.CheckConstraint(
                condition=~Q(quantity_mode="unlimited") | Q(quantity_total__isnull=True),
                name="listing_unlimited_has_no_total",
            ),
            # BR-204: available = total − reserved − sold for tracked stock.
            models.CheckConstraint(
                condition=Q(quantity_mode="unlimited")
                | Q(quantity_total=F("quantity_available") + F("quantity_reserved") + F("quantity_sold")),
                name="listing_stock_balances",
            ),
            models.CheckConstraint(
                condition=Q(price_usd__isnull=True) | Q(price_usd__gt=0), name="listing_price_positive"
            ),
            models.CheckConstraint(
                condition=Q(commission_rate_override__isnull=True)
                | Q(commission_rate_override__gte=0, commission_rate_override__lte=100),
                name="listing_commission_range",
            ),
            models.CheckConstraint(
                condition=~Q(deposit_type="percentage") | Q(deposit_value__gt=0, deposit_value__lte=100),
                name="listing_deposit_percentage_range",
            ),
            models.CheckConstraint(
                condition=~Q(deposit_type="fixed") | Q(deposit_value__gt=0), name="listing_deposit_fixed_positive"
            ),
            # BR-212: never active without approved pricing; fixed price needs a price.
            models.CheckConstraint(
                condition=~Q(status="active") | Q(pricing_approved_at__isnull=False),
                name="listing_active_requires_pricing",
            ),
            models.CheckConstraint(
                condition=~Q(sale_mode="fixed_price", status="active") | Q(price_usd__isnull=False),
                name="listing_fixed_price_has_price",
            ),
            models.CheckConstraint(
                condition=~Q(sale_mode="auction") | Q(quantity_mode="unique"), name="listing_auction_is_unique"
            ),
            models.CheckConstraint(condition=Q(max_per_order__gte=1), name="listing_max_per_order_positive"),
            models.CheckConstraint(
                condition=Q(starts_at__isnull=True) | Q(ends_at__isnull=True) | Q(ends_at__gt=F("starts_at")),
                name="listing_window_ordered",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.artwork} — {self.get_status_display()}"

    @property
    def tracks_stock(self) -> bool:
        return self.quantity_mode != QuantityMode.UNLIMITED

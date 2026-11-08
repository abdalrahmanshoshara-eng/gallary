"""
Settlements (BR-704…706): what the platform owes the artist — or, for auction-request works,
the owner — for each sold item. Created when the order is CONFIRMED, from the order item's
snapshot (never recomputed). Payment happens outside the platform; only the record is kept.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class SettlementStatus(models.TextChoices):
    PENDING = "pending", "مستحقة"
    ON_HOLD = "on_hold", "معلّقة"
    PAID = "paid", "مدفوعة"
    CANCELLED = "cancelled", "ملغاة"


class Settlement(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order_item = models.OneToOneField("orders.OrderItem", on_delete=models.PROTECT, related_name="settlement")
    payee_type = models.CharField(max_length=8)  # artist / owner (BR-705), from the item snapshot
    artist = models.ForeignKey(
        "artists.Artist", null=True, blank=True, on_delete=models.PROTECT, related_name="settlements"
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="settlements"
    )
    payee_name = models.CharField(max_length=200)  # who is paid, as known when the sale was confirmed
    payee_key = models.CharField(max_length=40, db_index=True)  # groups one payee: artist:<id> / owner:<id> / name:<…>
    currency = models.CharField(max_length=3, default="USD")
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    platform_commission = models.DecimalField(max_digits=12, decimal_places=2)
    payee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=SettlementStatus.choices, default=SettlementStatus.PENDING)
    status_reason = models.TextField(blank=True)
    paid_at = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تسوية"
        verbose_name_plural = "التسويات"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"], name="settlement_status_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(gross_amount=F("platform_commission") + F("payee_amount")), name="settlement_amounts_add_up"
            ),
            models.CheckConstraint(condition=Q(payee_amount__gte=0), name="settlement_payee_non_negative"),
            # BR-706: a paid settlement always carries its date and transfer reference.
            models.CheckConstraint(
                condition=~Q(status="paid") | (Q(paid_at__isnull=False) & ~Q(reference="")),
                name="settlement_paid_has_reference",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.payee_name}: {self.payee_amount} ({self.status})"

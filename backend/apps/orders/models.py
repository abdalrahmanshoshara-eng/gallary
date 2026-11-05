"""
Orders (BUSINESS_RULES §3–4, ERD orders).

A cart checkout becomes ONE order with several items. Stock is reserved for 24 hours until
the deposit is confirmed (BR-306/307). Money is never computed in the browser: every
amount is a snapshot taken under locks at checkout and recomputed only from items and
confirmed payment records.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.artworks.models import Artwork
from apps.listings.models import Listing


class OrderStatus(models.TextChoices):
    PENDING_DEPOSIT = "pending_deposit", "بانتظار العربون"
    DEPOSIT_CONFIRMED = "deposit_confirmed", "تم تأكيد العربون"
    PAYMENT_PENDING = "payment_pending", "بانتظار استكمال الدفع"
    CONFIRMED = "confirmed", "مؤكد"
    COMPLETED = "completed", "مكتمل"
    EXPIRED = "expired", "منتهي المهلة"
    CANCELLED_BY_CUSTOMER = "cancelled_by_customer", "ألغاه العميل"
    CANCELLED_BY_PLATFORM = "cancelled_by_platform", "ألغته المنصة"


FINAL_STATUSES = frozenset(
    {
        OrderStatus.COMPLETED,
        OrderStatus.EXPIRED,
        OrderStatus.CANCELLED_BY_CUSTOMER,
        OrderStatus.CANCELLED_BY_PLATFORM,
    }
)
OPEN_STATUSES = frozenset(set(OrderStatus.values) - FINAL_STATUSES)


class OrderSource(models.TextChoices):
    CART = "cart", "العربة"
    AUCTION = "auction", "مزاد"


class OrderDepositType(models.TextChoices):
    PER_ITEM = "per_item", "حسب إعداد كل عرض"  # cart orders (BR-409)
    FIXED = "fixed", "مبلغ ثابت"
    PERCENTAGE = "percentage", "نسبة"
    CUSTOM = "custom", "مخصص"


class DepositStatus(models.TextChoices):
    PENDING = "pending", "بانتظار الدفع"
    CONFIRMED = "confirmed", "مؤكد"
    FORFEITED = "forfeited", "مُصادَر"
    REFUND_DUE = "refund_due", "مستحق الاسترداد"
    REFUNDED = "refunded", "مُسترد"


class PaymentStatus(models.TextChoices):
    UNPAID = "unpaid", "غير مدفوع"
    PARTIALLY_PAID = "partially_paid", "مدفوع جزئياً"
    PAID = "paid", "مدفوع بالكامل"
    REFUNDED = "refunded", "مُسترد"


class OrderNumberSequence(models.Model):
    """Yearly counter locked with FOR UPDATE (BR-304) — never max(id)."""

    year = models.PositiveSmallIntegerField(primary_key=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.year}: {self.last_value}"


class Order(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order_number = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    source = models.CharField(max_length=10, choices=OrderSource.choices, default=OrderSource.CART)
    status = models.CharField(max_length=24, choices=OrderStatus.choices, default=OrderStatus.PENDING_DEPOSIT)
    currency = models.CharField(max_length=3, default="USD", editable=False)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_type = models.CharField(max_length=12, choices=OrderDepositType.choices, default=OrderDepositType.PER_ITEM)
    deposit_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deposit_due = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_status = models.CharField(max_length=12, choices=DepositStatus.choices, default=DepositStatus.PENDING)
    payment_status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # derived, stored for speed

    reservation_expires_at = models.DateTimeField()
    payment_deadline = models.DateTimeField(null=True, blank=True)  # auction orders (Phase 6)
    policy_version = models.CharField(max_length=20)
    policy_accepted_at = models.DateTimeField()

    # Contact and delivery snapshot taken at checkout (the profile may change later).
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=16)
    contact_email = models.EmailField(blank=True)
    governorate = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address_line = models.CharField(max_length=255, blank=True)

    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    cancelled_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(default=timezone.now)  # same instant as the 24 h deadline (BR-306)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "طلب"
        verbose_name_plural = "الطلبات"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "reservation_expires_at"], name="order_expiry_idx"),
            models.Index(fields=["user", "-created_at"], name="order_user_recent_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="order_subtotal_non_negative"),
            # BR-403: 0 < deposit_due ≤ subtotal (an emptied order is cancelled, never left at 0).
            models.CheckConstraint(
                condition=Q(deposit_due__gt=0, deposit_due__lte=models.F("subtotal")), name="order_deposit_in_range"
            ),
            models.CheckConstraint(condition=Q(currency="USD"), name="order_currency_usd"),
        ]

    def __str__(self) -> str:
        return self.order_number

    @property
    def is_final(self) -> bool:
        return self.status in FINAL_STATUSES


class OrderItemStatus(models.TextChoices):
    ACTIVE = "active", "فعّال"
    REMOVED = "removed", "أُزيل"


class PayeeType(models.TextChoices):
    ARTIST = "artist", "الفنان"
    OWNER = "owner", "المالك"


class OrderItem(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="order_items")
    artwork = models.ForeignKey(Artwork, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveSmallIntegerField()
    title_snapshot = models.CharField(max_length=250)
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    payee_amount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    payee_type_snapshot = models.CharField(max_length=8, choices=PayeeType.choices, default=PayeeType.ARTIST)
    deposit_amount_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=8, choices=OrderItemStatus.choices, default=OrderItemStatus.ACTIVE)
    removed_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price_snapshot__gt=0), name="order_item_price_positive"),
            models.CheckConstraint(
                condition=Q(payee_amount_snapshot=models.F("line_total") - models.F("commission_amount_snapshot")),
                name="order_item_payee_balances",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}:{self.title_snapshot}×{self.quantity}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )  # null = system
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status} → {self.to_status}"


class PaymentKind(models.TextChoices):
    DEPOSIT = "deposit", "عربون"
    PAYMENT = "payment", "دفعة"
    REFUND = "refund", "استرداد"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "نقداً"
    BANK_TRANSFER = "bank_transfer", "تحويل مصرفي"
    MONEY_TRANSFER = "money_transfer", "حوالة مالية"
    OTHER = "other", "أخرى"


class PaymentRecordStatus(models.TextChoices):
    RECORDED = "recorded", "مسجّل (بانتظار التأكيد)"
    CONFIRMED = "confirmed", "مؤكد"
    VOIDED = "voided", "مُلغى"


class PaymentRecord(models.Model):
    """Manual payment ledger (BR-407). Confirmed records are never edited; corrections are
    new records (e.g. a refund). Only unconfirmed records can be voided."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    kind = models.CharField(max_length=8, choices=PaymentKind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=16, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=PaymentRecordStatus.choices, default=PaymentRecordStatus.RECORDED)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=~Q(status="confirmed") | Q(confirmed_by__isnull=False, confirmed_at__isnull=False),
                name="payment_confirmed_has_confirmer",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.kind} {self.amount} ({self.status})"


class DeliveryStatus(models.TextChoices):
    NOT_STARTED = "not_started", "لم يبدأ"
    IN_TRANSIT = "in_transit", "قيد التوصيل"
    DELIVERED = "delivered", "تم التسليم"


class DeliveryMethod(models.TextChoices):
    PICKUP = "pickup", "استلام من المنصة"
    COURIER = "courier", "شركة توصيل"
    PLATFORM = "platform", "توصيل من المنصة"
    OTHER = "other", "أخرى"


class Delivery(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")
    method = models.CharField(max_length=10, choices=DeliveryMethod.choices, blank=True)
    carrier_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=DeliveryStatus.choices, default=DeliveryStatus.NOT_STARTED)
    delivered_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.order_id}: {self.status}"

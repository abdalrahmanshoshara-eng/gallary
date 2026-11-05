"""
Auctions (BR-501…517) and auction requests (BR-601…607).

PostgreSQL is the source of truth: bids are accepted only under a row lock on the auction
and against the database clock (BR-505/507). Every state change bumps `version`, which is
the `seq` of realtime events (BR-507b), so clients can detect gaps and resync.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.listings.models import Listing
from apps.media.models import ImageAsset


class AuctionStatus(models.TextChoices):
    DRAFT = "draft", "مسودة"
    SCHEDULED = "scheduled", "مجدول"
    LIVE = "live", "جارٍ"
    ENDED = "ended", "انتهى"
    PENDING_WINNER_PAYMENT = "pending_winner_payment", "بانتظار دفع الفائز"
    AWARDED = "awarded", "مُرسى"
    CANCELLED = "cancelled", "ملغى"


FINAL_AUCTION_STATUSES = frozenset({AuctionStatus.ENDED, AuctionStatus.AWARDED, AuctionStatus.CANCELLED})


class AuctionOutcome(models.TextChoices):
    SOLD = "sold", "بيع"
    NO_SALE = "no_sale", "لا مزايدات"
    RESERVE_NOT_MET = "reserve_not_met", "لم يُبلغ السعر الأدنى"
    UNPAID = "unpaid", "لم يُدفع"


class NonPaymentPolicy(models.TextChoices):
    OFFER_NEXT_BIDDER = "offer_next_bidder", "عرض على المزايد التالي"
    CANCEL_AWARD = "cancel_award", "إلغاء الإرساء"


class Auction(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    listing = models.OneToOneField(Listing, on_delete=models.PROTECT, related_name="auction")
    title = models.CharField(max_length=250)
    terms = models.TextField(blank=True)

    starting_price = models.DecimalField(max_digits=12, decimal_places=2)
    minimum_increment = models.DecimalField(max_digits=12, decimal_places=2)
    reserve_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    original_ends_at = models.DateTimeField()
    extension_window_sec = models.PositiveIntegerField(default=300)
    extension_duration_sec = models.PositiveIntegerField(default=300)
    max_extensions = models.PositiveSmallIntegerField(default=10)
    extensions_count = models.PositiveSmallIntegerField(default=0)

    winner_deposit_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("50.00"))
    winner_payment_window_sec = models.PositiveIntegerField(default=3600, editable=False)  # fixed rule (1 hour)
    non_payment_policy = models.CharField(
        max_length=20, choices=NonPaymentPolicy.choices, default=NonPaymentPolicy.OFFER_NEXT_BIDDER
    )

    status = models.CharField(max_length=24, choices=AuctionStatus.choices, default=AuctionStatus.DRAFT)
    outcome = models.CharField(max_length=16, choices=AuctionOutcome.choices, blank=True)
    version = models.BigIntegerField(default=0)
    bid_count = models.PositiveIntegerField(default=0)
    highest_bid = models.ForeignKey("Bid", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    current_winner_bid = models.ForeignKey("Bid", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    winner_declared_at = models.DateTimeField(null=True, blank=True)
    payment_deadline = models.DateTimeField(null=True, blank=True)
    winner_order_id = models.BigIntegerField(null=True, blank=True)  # orders.Order pk (orders sit below auctions)
    cancelled_reason = models.TextField(blank=True)
    source_request = models.ForeignKey(
        "AuctionRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "مزاد"
        verbose_name_plural = "المزادات"
        ordering = ["-starts_at"]
        indexes = [
            models.Index(fields=["status", "starts_at"], name="auction_status_start_idx"),
            models.Index(fields=["status", "ends_at"], name="auction_status_end_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="auction_window_ordered"),
            models.CheckConstraint(condition=Q(starting_price__gt=0), name="auction_starting_price_positive"),
            models.CheckConstraint(condition=Q(minimum_increment__gt=0), name="auction_increment_positive"),
            models.CheckConstraint(
                condition=Q(reserve_price__isnull=True) | Q(reserve_price__gte=F("starting_price")),
                name="auction_reserve_at_least_start",
            ),
            # BR-410: the winner's deposit is never below 50%.
            models.CheckConstraint(
                condition=Q(winner_deposit_percent__gte=50, winner_deposit_percent__lte=100),
                name="auction_winner_deposit_at_least_50",
            ),
            models.CheckConstraint(
                condition=Q(extensions_count__lte=F("max_extensions")), name="auction_extension_cap"
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def minimum_next_bid(self) -> Decimal:
        if self.current_price is None:
            return self.starting_price
        return self.current_price + self.minimum_increment


class BidStatus(models.TextChoices):
    VALID = "valid", "سارية (الأعلى)"
    OUTBID = "outbid", "تم تجاوزها"
    WINNING = "winning", "فائزة"
    NON_PAYMENT = "non_payment", "لم يُدفع"
    VOIDED = "voided", "ملغاة"


class Bid(models.Model):
    """Bids are never edited or deleted (BR-509)."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.PROTECT, related_name="bids")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bids")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=BidStatus.choices, default=BidStatus.VALID)
    void_reason = models.TextField(blank=True)
    bidder_alias = models.PositiveIntegerField()  # stable per user within an auction (BR-507c)
    idempotency_key = models.CharField(max_length=64)
    auction_version = models.BigIntegerField()
    created_at = models.DateTimeField()  # PostgreSQL clock at acceptance (BR-505)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-amount", "created_at"]
        indexes = [models.Index(fields=["auction", "-amount", "created_at"], name="bid_ranking_idx")]
        constraints = [
            models.UniqueConstraint(fields=["user", "idempotency_key"], name="bid_idempotent_per_user"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="bid_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.auction_id}: {self.amount} (#{self.bidder_alias})"


class AuctionStatusHistory(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.auction_id}: {self.from_status} → {self.to_status}"


# --- auction requests (BR-601…607) --------------------------------------------------------------
class RequestStatus(models.TextChoices):
    SUBMITTED = "submitted", "مُرسل"
    UNDER_REVIEW = "under_review", "قيد المراجعة"
    NEEDS_MORE_INFO = "needs_more_info", "بحاجة لمعلومات إضافية"
    NEGOTIATION = "negotiation", "قيد التفاوض"
    APPROVED = "approved", "مقبول"
    REJECTED = "rejected", "مرفوض"
    WITHDRAWN = "withdrawn", "مسحوب"


FINAL_REQUEST_STATUSES = frozenset({RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.WITHDRAWN})


class AuctionRequest(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="auction_requests")
    work_title = models.CharField(max_length=250)
    work_description = models.TextField()
    artist_name = models.CharField(max_length=200)
    artist_info = models.TextField(blank=True)
    category_hint = models.CharField(max_length=120, blank=True)
    dimensions_text = models.CharField(max_length=120, blank=True)
    year_text = models.CharField(max_length=40, blank=True)
    expected_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    contact_phone = models.CharField(max_length=16)
    customer_notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=RequestStatus.choices, default=RequestStatus.SUBMITTED)
    agreed_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    commission_agreed_at = models.DateTimeField(null=True, blank=True)
    commission_agreed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resulting_artwork = models.ForeignKey(
        "artworks.Artwork", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resulting_auction = models.ForeignKey(Auction, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "طلب مزاد"
        verbose_name_plural = "طلبات المزاد"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(agreed_commission_rate__isnull=True)
                | Q(agreed_commission_rate__gte=0, agreed_commission_rate__lte=100),
                name="auction_request_commission_range",
            ),
            # BR-606: never approved without an agreed platform share (zero is allowed).
            models.CheckConstraint(
                condition=~Q(status="approved") | Q(agreed_commission_rate__isnull=False),
                name="auction_request_approved_has_commission",
            ),
            models.CheckConstraint(
                condition=Q(expected_price__isnull=True) | Q(expected_price__gt=0),
                name="auction_request_price_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.work_title


class AuctionRequestImage(models.Model):
    request = models.ForeignKey(AuctionRequest, on_delete=models.CASCADE, related_name="images")
    asset = models.OneToOneField(ImageAsset, on_delete=models.PROTECT, related_name="+")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.request_id}: {self.asset_id}"


class NoteVisibility(models.TextChoices):
    INTERNAL = "internal", "داخلية"
    CUSTOMER = "customer", "رسالة للعميل"


class AuctionRequestNote(models.Model):
    request = models.ForeignKey(AuctionRequest, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    visibility = models.CharField(max_length=10, choices=NoteVisibility.choices)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.request_id}: {self.visibility}"


class RequestStatusHistory(models.Model):
    request = models.ForeignKey(AuctionRequest, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.request_id}: {self.to_status}"

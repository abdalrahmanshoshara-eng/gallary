"""
Listing lifecycle, pricing and inventory (BR-201…213, BR-701, BR-402).

- Catalog editors create and manage offers; only the Super Admin sets price, commission and
  deposit (BR-212), and an offer cannot become ACTIVE before that approval.
- Stock changes (reserve / confirm / release) always lock the listing row first
  (SELECT … FOR UPDATE, BR-206). Phase 5 (orders) builds on these primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.artists.models import ArtistStatus
from apps.artworks.models import Artwork, PublicationStatus
from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.core.models import DepositType, SiteSetting

from .models import Listing, ListingStatus, QuantityMode, SaleMode

CENT = Decimal("0.01")


class ListingStateError(ConflictError):
    code = "INVALID_LISTING_STATE"
    message = "لا يمكن تنفيذ هذه العملية في حالة العرض الحالية."


class ActivationError(ConflictError):
    code = "LISTING_NOT_ACTIVATABLE"
    message = "لا يمكن تفعيل العرض قبل استيفاء متطلباته."


class AlreadyActiveError(ConflictError):
    code = "LISTING_ALREADY_ACTIVE"
    message = "لهذا العمل عرض نشط آخر. اسحبه أولاً."


class InsufficientStockError(ConflictError):
    code = "INSUFFICIENT_STOCK"
    message = "الكمية المطلوبة غير متوفرة."


class NotPurchasableError(ConflictError):
    code = "NOT_PURCHASABLE"
    message = "هذا العرض غير متاح للشراء حالياً."


def _invalid(field: str, message: str) -> ConflictError:
    return ConflictError(message, code="VALIDATION_ERROR", http_status=400, details={field: [message]})


# --- effective terms (BR-701, BR-402) ---------------------------------------------------------
@dataclass(frozen=True)
class DepositTerms:
    type: str
    value: Decimal

    def amount_for(self, line_total: Decimal, quantity: int = 1) -> Decimal:
        if self.type == DepositType.FIXED:
            amount = self.value * quantity
        else:
            amount = (line_total * self.value / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
        return min(amount, line_total)  # BR-403: deposit never exceeds the subtotal


def commission_rate(listing: Listing, settings: SiteSetting | None = None) -> Decimal:
    if listing.commission_rate_override is not None:
        return listing.commission_rate_override
    return (settings or SiteSetting.load()).default_commission_rate


def deposit_terms(listing: Listing, settings: SiteSetting | None = None) -> DepositTerms:
    if listing.deposit_type and listing.deposit_value is not None:
        return DepositTerms(listing.deposit_type, listing.deposit_value)
    s = settings or SiteSetting.load()
    return DepositTerms(s.default_deposit_type, s.default_deposit_value)


def split_commission(price: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """BR-702: commission = round(price × rate / 100, 2); payee = price − commission."""
    commission = (price * rate / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    return commission, price - commission


# --- availability ----------------------------------------------------------------------------------
def artwork_is_sellable(artwork: Artwork) -> bool:
    return (
        artwork.publication_status == PublicationStatus.PUBLISHED
        and artwork.archived_at is None
        and (artwork.artist_id is None or artwork.artist.status == ArtistStatus.ACTIVE)
    )


def in_window(listing: Listing, now=None) -> bool:
    now = now or timezone.now()
    return (listing.starts_at is None or listing.starts_at <= now) and (
        listing.ends_at is None or listing.ends_at > now
    )


def purchase_problem(listing: Listing, quantity: int = 1, now=None) -> str | None:
    """BR-209. Returns None when `quantity` can be bought now, otherwise a reason code."""
    if listing.sale_mode != SaleMode.FIXED_PRICE:
        return "auction_only"
    if listing.status != ListingStatus.ACTIVE:
        return "sold_out" if listing.status == ListingStatus.SOLD_OUT else "not_active"
    if not artwork_is_sellable(listing.artwork):
        return "artwork_unavailable"
    if not in_window(listing, now):
        now = now or timezone.now()
        return "not_started" if listing.starts_at and listing.starts_at > now else "ended"
    if quantity < 1 or quantity > listing.max_per_order:
        return "quantity_limit"
    if listing.tracks_stock and listing.quantity_available < quantity:
        if listing.quantity_available == 0:
            return "reserved" if listing.quantity_reserved else "sold_out"
        return "insufficient_stock"
    return None


# --- create / update -------------------------------------------------------------------------------
def _stock_for(mode: str, total: int | None) -> dict:
    if mode == QuantityMode.UNIQUE:
        return {"quantity_total": 1, "quantity_available": 1}
    if mode == QuantityMode.LIMITED:
        if not total or total < 2:
            raise _invalid("quantity_total", "الكمية المحدودة يجب أن تكون 2 أو أكثر.")
        return {"quantity_total": total, "quantity_available": total}
    return {"quantity_total": None, "quantity_available": 0}


def _check_window(starts_at, ends_at) -> None:
    if starts_at and ends_at and ends_at <= starts_at:
        raise _invalid("ends_at", "تاريخ الانتهاء يجب أن يكون بعد تاريخ البدء.")


@transaction.atomic
def create_listing(
    *,
    actor,
    artwork: Artwork,
    quantity_mode: str = QuantityMode.UNIQUE,
    quantity_total: int | None = None,
    max_per_order: int = 1,
    starts_at=None,
    ends_at=None,
    internal_notes: str = "",
) -> Listing:
    if artwork.archived_at is not None:
        raise ConflictError("لا يمكن إنشاء عرض لعمل مؤرشف.", code="ARTWORK_ARCHIVED")
    _check_window(starts_at, ends_at)
    if quantity_mode == QuantityMode.UNIQUE:
        max_per_order = 1
    listing = Listing.objects.create(
        artwork=artwork,
        sale_mode=SaleMode.FIXED_PRICE,
        quantity_mode=quantity_mode,
        max_per_order=max(1, max_per_order),
        starts_at=starts_at,
        ends_at=ends_at,
        internal_notes=internal_notes,
        created_by=actor,
        **_stock_for(quantity_mode, quantity_total),
    )
    audit.record(
        actor=actor,
        action="listing.created",
        entity=listing,
        changes={"artwork": str(artwork.public_id), "quantity_mode": quantity_mode, "quantity_total": quantity_total},
    )
    return listing


def _lock(listing: Listing) -> Listing:
    return (
        Listing.objects.select_for_update(of=("self",)).select_related("artwork", "artwork__artist").get(pk=listing.pk)
    )


@transaction.atomic
def update_listing(listing: Listing, *, actor, data: dict) -> Listing:
    """Editors' fields. Stock mode is fixed once the offer has been active; a limited total
    can still grow or shrink down to what is already reserved and sold."""
    listing = _lock(listing)
    if listing.status in (ListingStatus.ENDED, ListingStatus.WITHDRAWN):
        raise ListingStateError("العرض مغلق؛ أنشئ عرضاً جديداً لإعادة البيع (BR-211).")
    changes: dict[str, object] = {}
    mode = data.get("quantity_mode", listing.quantity_mode)
    total = data.get("quantity_total", listing.quantity_total)

    if mode != listing.quantity_mode:
        if listing.status != ListingStatus.DRAFT or listing.quantity_reserved or listing.quantity_sold:
            raise ListingStateError("لا يمكن تغيير نوع الكمية بعد تفعيل العرض.")
        changes["quantity_mode"] = {"from": listing.quantity_mode, "to": mode}
        listing.quantity_mode = mode
        for field, value in _stock_for(mode, total).items():
            setattr(listing, field, value)
        if mode == QuantityMode.UNIQUE:
            listing.max_per_order = 1
    elif mode == QuantityMode.LIMITED and total != listing.quantity_total:
        committed = listing.quantity_reserved + listing.quantity_sold
        if not total or total < 2 or total < committed:
            raise _invalid("quantity_total", f"الكمية يجب ألا تقل عن 2 ولا عن المحجوز والمباع ({committed}).")
        changes["quantity_total"] = {"from": listing.quantity_total, "to": total}
        listing.quantity_total = total
        listing.quantity_available = total - committed
        if listing.status == ListingStatus.SOLD_OUT and listing.quantity_available > 0:
            listing.status = ListingStatus.ACTIVE
        elif (
            listing.status == ListingStatus.ACTIVE and listing.quantity_available == 0 and not listing.quantity_reserved
        ):
            listing.status = ListingStatus.SOLD_OUT

    for field in ("max_per_order", "starts_at", "ends_at", "internal_notes"):
        if field in data and data[field] != getattr(listing, field):
            if field != "internal_notes":
                changes[field] = {"from": str(getattr(listing, field)), "to": str(data[field])}
            setattr(listing, field, data[field])
    if listing.quantity_mode == QuantityMode.UNIQUE:
        listing.max_per_order = 1
    if listing.max_per_order < 1:
        raise _invalid("max_per_order", "الحد الأقصى للطلب الواحد يجب أن يكون 1 على الأقل.")
    _check_window(listing.starts_at, listing.ends_at)
    listing.save()
    if changes:
        audit.record(actor=actor, action="listing.updated", entity=listing, changes=changes)
    return listing


@transaction.atomic
def set_pricing(
    listing: Listing,
    *,
    actor,
    price_usd: Decimal,
    commission_rate_override: Decimal | None,
    deposit_type: str,
    deposit_value: Decimal | None,
) -> Listing:
    """Super Admin only (enforced by the API permission). Approves the pricing (BR-212).
    Existing orders keep their snapshot (BR-210)."""
    listing = _lock(listing)
    if listing.status in (ListingStatus.ENDED, ListingStatus.WITHDRAWN):
        raise ListingStateError()
    if price_usd is None or price_usd <= 0:
        raise _invalid("price_usd", "السعر يجب أن يكون أكبر من صفر.")
    if commission_rate_override is not None and not (0 <= commission_rate_override <= 100):
        raise _invalid("commission_rate_override", "نسبة العمولة بين 0 و100.")
    if deposit_type:
        if deposit_value is None or deposit_value <= 0:
            raise _invalid("deposit_value", "قيمة العربون يجب أن تكون أكبر من صفر.")
        if deposit_type == DepositType.PERCENTAGE and deposit_value > 100:
            raise _invalid("deposit_value", "نسبة العربون لا تتجاوز 100%.")
        if deposit_type == DepositType.FIXED and deposit_value > price_usd:
            raise _invalid("deposit_value", "العربون الثابت لا يتجاوز سعر القطعة.")
    else:
        deposit_value = None  # inherit the platform default

    before = {
        "price_usd": listing.price_usd,
        "commission_rate_override": listing.commission_rate_override,
        "deposit_type": listing.deposit_type,
        "deposit_value": listing.deposit_value,
    }
    listing.price_usd = price_usd
    listing.commission_rate_override = commission_rate_override
    listing.deposit_type = deposit_type or ""
    listing.deposit_value = deposit_value
    listing.pricing_approved_by = actor
    listing.pricing_approved_at = timezone.now()
    listing.save()
    after = {
        "price_usd": listing.price_usd,
        "commission_rate_override": listing.commission_rate_override,
        "deposit_type": listing.deposit_type,
        "deposit_value": listing.deposit_value,
    }
    changes = {k: {"from": str(before[k]), "to": str(after[k])} for k in after if before[k] != after[k]}
    audit.record(actor=actor, action="listing.pricing_approved", entity=listing, changes=changes)
    return listing


def activation_problems(listing: Listing) -> list[str]:
    problems = []
    if listing.pricing_approved_at is None or listing.price_usd is None:
        problems.append("pricing_not_approved")
    if not artwork_is_sellable(listing.artwork):
        problems.append("artwork_not_public")
    if listing.tracks_stock and listing.quantity_available < 1:
        problems.append("no_stock")
    if listing.ends_at and listing.ends_at <= timezone.now():
        problems.append("window_ended")
    return problems


@transaction.atomic
def activate(listing: Listing, *, actor) -> Listing:
    listing = _lock(listing)
    if listing.status != ListingStatus.DRAFT:
        raise ListingStateError()
    problems = activation_problems(listing)
    if problems:
        raise ActivationError(details={"problems": problems})
    listing.status = ListingStatus.ACTIVE
    listing.activated_at = timezone.now()
    try:
        with transaction.atomic():
            listing.save(update_fields=["status", "activated_at", "updated_at"])
    except IntegrityError:
        raise AlreadyActiveError() from None
    audit.record(actor=actor, action="listing.activated", entity=listing)
    return listing


@transaction.atomic
def withdraw(listing: Listing, *, actor, reason: str = "") -> Listing:
    listing = _lock(listing)
    if listing.status in (ListingStatus.ENDED, ListingStatus.WITHDRAWN):
        raise ListingStateError()
    if listing.quantity_reserved:
        raise ConflictError(
            "للعرض حجوزات قائمة؛ عالجها قبل سحبه.",
            code="LISTING_HAS_RESERVATIONS",
            details={"reserved": listing.quantity_reserved},
        )
    listing.status = ListingStatus.WITHDRAWN
    listing.closed_at = timezone.now()
    listing.save(update_fields=["status", "closed_at", "updated_at"])
    audit.record(actor=actor, action="listing.withdrawn", entity=listing, reason=reason)
    return listing


@transaction.atomic
def delete_draft(listing: Listing, *, actor) -> None:
    listing = _lock(listing)
    if listing.status != ListingStatus.DRAFT or listing.activated_at or listing.quantity_sold:
        raise ListingStateError("تُحذف المسودات التي لم تُفعَّل فقط؛ اسحب العرض بدلاً من ذلك.")
    audit.record(actor=actor, action="listing.deleted", entity=listing)
    listing.delete()


def end_expired_listings(now=None) -> int:
    """Beat task: ACTIVE offers past `ends_at` become ENDED (reservations keep their stock)."""
    now = now or timezone.now()
    ended = 0
    for pk in Listing.objects.filter(status=ListingStatus.ACTIVE, ends_at__lte=now).values_list("pk", flat=True):
        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(pk=pk)
            if listing.status == ListingStatus.ACTIVE and listing.ends_at and listing.ends_at <= now:
                listing.status = ListingStatus.ENDED
                listing.closed_at = now
                listing.save(update_fields=["status", "closed_at", "updated_at"])
                audit.record(actor=None, action="listing.ended", entity=listing)
                ended += 1
    return ended


# --- inventory primitives (BR-204…207) — callers own the surrounding transaction ----------------
def _derive_sold_out(listing: Listing) -> None:
    if not listing.tracks_stock:
        return
    if listing.status == ListingStatus.ACTIVE and listing.quantity_available == 0 and listing.quantity_reserved == 0:
        listing.status = ListingStatus.SOLD_OUT
        listing.closed_at = timezone.now()
    elif listing.status == ListingStatus.SOLD_OUT and listing.quantity_available > 0:
        listing.status = ListingStatus.ACTIVE
        listing.closed_at = None


def reserve(listing_id: int, quantity: int) -> Listing:
    """available −= q, reserved += q. Raises if the offer cannot be bought now."""
    listing = (
        Listing.objects.select_for_update(of=("self",)).select_related("artwork", "artwork__artist").get(pk=listing_id)
    )
    problem = purchase_problem(listing, quantity)
    if problem in ("sold_out", "reserved", "insufficient_stock"):
        raise InsufficientStockError(details={"available": listing.quantity_available, "reason": problem})
    if problem:
        raise NotPurchasableError(details={"reason": problem})
    if listing.tracks_stock:
        listing.quantity_available -= quantity
    listing.quantity_reserved += quantity
    listing.save(update_fields=["quantity_available", "quantity_reserved", "updated_at"])
    return listing


def confirm_sale(listing_id: int, quantity: int) -> Listing:
    """reserved −= q, sold += q; derives SOLD_OUT."""
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    if quantity < 1 or listing.quantity_reserved < quantity:
        raise ListingStateError("لا يوجد حجز كافٍ لتأكيد البيع.")
    listing.quantity_reserved -= quantity
    listing.quantity_sold += quantity
    _derive_sold_out(listing)
    listing.save(update_fields=["quantity_reserved", "quantity_sold", "status", "closed_at", "updated_at"])
    return listing


def release(listing_id: int, quantity: int) -> Listing:
    """Expiry/cancellation before sale: reserved −= q, available += q (reopens SOLD_OUT)."""
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    if quantity < 1 or listing.quantity_reserved < quantity:
        raise ListingStateError("لا يوجد حجز كافٍ لتحريره.")
    listing.quantity_reserved -= quantity
    if listing.tracks_stock:
        listing.quantity_available += quantity
    _derive_sold_out(listing)
    listing.save(update_fields=["quantity_available", "quantity_reserved", "status", "closed_at", "updated_at"])
    return listing


def revert_sale(listing_id: int, quantity: int) -> Listing:
    """A confirmed sale is cancelled by the platform: sold −= q, available += q."""
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    if quantity < 1 or listing.quantity_sold < quantity:
        raise ListingStateError("لا توجد كمية مباعة كافية لإلغائها.")
    listing.quantity_sold -= quantity
    if listing.tracks_stock:
        listing.quantity_available += quantity
    _derive_sold_out(listing)
    listing.save(update_fields=["quantity_available", "quantity_sold", "status", "closed_at", "updated_at"])
    return listing

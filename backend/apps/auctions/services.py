"""
Auction workflow (BR-501…517).

Bidding rules (BR-505…510):
- A bid is accepted only inside a transaction holding `SELECT … FOR UPDATE` on the auction,
  against the PostgreSQL clock, using the stored `starts_at ≤ now < ends_at` — never the
  `status` field, so a late scheduler can never let a bid in after the end.
- Every state change bumps `version`; realtime events carry it as `seq`.
- Bids are idempotent per (user, Idempotency-Key) and are never edited or deleted.

Time transitions run in `tick()` (Beat every 5 s) and lazily before reads (`refresh`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.artworks import services as artwork_services
from apps.artworks.models import Artwork, PublicationStatus
from apps.audit import services as audit
from apps.core.errors import AppError, ConflictError, PermissionDeniedError
from apps.core.events import publish_on_commit
from apps.listings import services as listing_services
from apps.listings.models import Listing, ListingStatus
from apps.orders import services as order_services
from apps.orders.models import Order, OrderStatus

from .events import AuctionEvent, BidderNotice
from .models import (
    FINAL_AUCTION_STATUSES,
    Auction,
    AuctionOutcome,
    AuctionStatus,
    AuctionStatusHistory,
    Bid,
    BidStatus,
    NonPaymentPolicy,
)

EDITABLE_FIELDS = (
    "title",
    "terms",
    "starting_price",
    "minimum_increment",
    "reserve_price",
    "starts_at",
    "ends_at",
    "extension_window_sec",
    "extension_duration_sec",
    "max_extensions",
    "winner_deposit_percent",
    "non_payment_policy",
)


# --- errors --------------------------------------------------------------------------------------
class AuctionStateError(ConflictError):
    code = "INVALID_AUCTION_STATE"
    message = "لا يمكن تنفيذ هذه العملية في حالة المزاد الحالية."


class BidRejected(ConflictError):
    code = "BID_REJECTED"
    message = "تعذّر قبول المزايدة."


def _invalid(field: str, message: str) -> AppError:
    return ConflictError(message, code="VALIDATION_ERROR", http_status=400, details={field: [message]})


# --- helpers ---------------------------------------------------------------------------------------
def db_now():
    """PostgreSQL's clock_timestamp(): the single reference clock for bids (BR-505)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT clock_timestamp()")
        return cursor.fetchone()[0]


def _lock(auction: Auction) -> Auction:
    return (
        Auction.objects.select_for_update(of=("self",)).select_related("listing", "listing__artwork").get(pk=auction.pk)
    )


def _bump(auction: Auction) -> int:
    auction.version += 1
    return auction.version


def state_data(auction: Auction) -> dict:
    """Public fields every event carries, so a client can always render from one message."""
    return {
        "status": auction.status,
        "outcome": auction.outcome,
        "current_price": str(auction.current_price) if auction.current_price is not None else None,
        "minimum_next_bid": str(auction.minimum_next_bid),
        "bid_count": auction.bid_count,
        "starts_at": auction.starts_at.isoformat(),
        "ends_at": auction.ends_at.isoformat(),
        "extensions_count": auction.extensions_count,
        "reserve_met": reserve_met(auction),
    }


def reserve_met(auction: Auction) -> bool | None:
    """Whether the hidden reserve is reached (None without a reserve); never the reserve itself."""
    if auction.reserve_price is None:
        return None
    return auction.current_price is not None and auction.current_price >= auction.reserve_price


def _emit(auction: Auction, event_type: str, **extra) -> None:
    publish_on_commit(
        AuctionEvent(
            auction_public_id=str(auction.public_id),
            seq=auction.version,
            type=event_type,
            data={**state_data(auction), **extra},
        )
    )


def _transition(auction: Auction, to: str, *, actor=None, reason: str = "", event: str | None = None, **extra) -> None:
    before = auction.status
    auction.status = to
    _bump(auction)
    auction.save()
    AuctionStatusHistory.objects.create(auction=auction, from_status=before, to_status=to, actor=actor, reason=reason)
    audit.record(actor=actor, action=f"auction.{to}", entity=auction, changes={"from": before, "to": to}, reason=reason)
    if event:
        _emit(auction, event, **extra)


# --- create / edit / schedule / cancel (BR-501…504) ----------------------------------------------
def _validate_terms(data: dict) -> None:
    starts, ends = data["starts_at"], data["ends_at"]
    if ends <= starts:
        raise _invalid("ends_at", "وقت الانتهاء يجب أن يكون بعد وقت البدء.")
    if data["starting_price"] <= 0:
        raise _invalid("starting_price", "السعر الافتتاحي يجب أن يكون أكبر من صفر.")
    if data["minimum_increment"] <= 0:
        raise _invalid("minimum_increment", "الحد الأدنى للزيادة يجب أن يكون أكبر من صفر.")
    reserve = data.get("reserve_price")
    if reserve is not None and reserve < data["starting_price"]:
        raise _invalid("reserve_price", "السعر الاحتياطي لا يقل عن السعر الافتتاحي.")
    pct = data.get("winner_deposit_percent", Decimal(50))
    if not (Decimal(50) <= pct <= Decimal(100)):
        raise _invalid("winner_deposit_percent", "عربون الفائز بين 50% و100% (BR-410).")


@transaction.atomic
def create_auction(
    *, actor, artwork: Artwork, data: dict, commission_rate_override=None, source_request=None
) -> Auction:
    if (
        artwork.listings.filter(status=ListingStatus.ACTIVE).exists()
        or Auction.objects.filter(listing__artwork=artwork).exclude(status__in=FINAL_AUCTION_STATUSES).exists()
    ):
        raise ConflictError("لهذا العمل عرض أو مزاد قائم.", code="ARTWORK_BUSY")
    data = {**data}
    data.setdefault("title", artwork.title)
    _validate_terms(data)
    listing = listing_services.create_auction_listing(
        actor=actor, artwork=artwork, commission_rate_override=commission_rate_override
    )
    auction = Auction.objects.create(
        listing=listing, original_ends_at=data["ends_at"], created_by=actor, source_request=source_request, **data
    )
    AuctionStatusHistory.objects.create(auction=auction, to_status=auction.status, actor=actor)
    audit.record(actor=actor, action="auction.created", entity=auction, changes={"artwork": str(artwork.public_id)})
    return auction


@transaction.atomic
def update_auction(auction: Auction, *, actor, data: dict) -> Auction:
    """BR-504: terms change only in DRAFT/SCHEDULED and before the start."""
    auction = _lock(auction)
    if auction.status not in (AuctionStatus.DRAFT, AuctionStatus.SCHEDULED) or db_now() >= auction.starts_at:
        raise AuctionStateError("لا يمكن تعديل شروط المزاد بعد بدئه.")
    merged = {f: data.get(f, getattr(auction, f)) for f in EDITABLE_FIELDS}
    _validate_terms(merged)
    changes = {}
    for field, value in merged.items():
        if getattr(auction, field) != value:
            changes[field] = {"from": str(getattr(auction, field)), "to": str(value)}
            setattr(auction, field, value)
    auction.original_ends_at = auction.ends_at
    if changes:
        _bump(auction)
        auction.save()
        audit.record(actor=actor, action="auction.updated", entity=auction, changes=changes)
        if auction.status == AuctionStatus.SCHEDULED:
            _emit(auction, "auction.updated")
    return auction


def _publishes_on_schedule(auction: Auction) -> bool:
    """A work from an auction request (BR-607) is published by its auction: the auction
    manager owns that flow end to end, content staff may still enrich the record."""
    artwork = auction.listing.artwork
    return (
        auction.source_request_id is not None
        and artwork.publication_status == PublicationStatus.DRAFT
        and artwork.archived_at is None
    )


def schedule_problems(auction: Auction) -> list[str]:
    problems = []
    artwork = auction.listing.artwork
    if _publishes_on_schedule(auction):
        problems.extend(artwork_services.publish_problems(artwork))
    elif not listing_services.artwork_is_sellable(artwork):
        problems.append("artwork_not_public")
    if auction.ends_at <= timezone.now():
        problems.append("window_passed")
    return problems


@transaction.atomic
def schedule(auction: Auction, *, actor) -> Auction:
    auction = _lock(auction)
    if auction.status != AuctionStatus.DRAFT:
        raise AuctionStateError()
    problems = schedule_problems(auction)
    if problems:
        raise ConflictError(
            "لا يمكن جدولة المزاد قبل استيفاء متطلباته.", code="AUCTION_NOT_SCHEDULABLE", details={"problems": problems}
        )
    if _publishes_on_schedule(auction):
        artwork_services.publish(auction.listing.artwork, actor=actor)
    listing_services.activate_auction_listing(auction.listing, actor=actor)
    _transition(auction, AuctionStatus.SCHEDULED, actor=actor, event="auction.scheduled")
    return auction


@transaction.atomic
def cancel(auction: Auction, *, actor, reason: str) -> Auction:
    """BR-517: a cancelled auction has no winner; a pending winner order is cancelled by the
    platform (deposit refundable)."""
    if not reason.strip():
        raise _invalid("reason", "سبب الإلغاء مطلوب.")
    auction = _lock(auction)
    if auction.status in FINAL_AUCTION_STATUSES:
        raise AuctionStateError()
    # The auction is cancelled first so the order signal below never offers it to another bidder.
    auction.cancelled_reason = reason.strip()
    _transition(auction, AuctionStatus.CANCELLED, actor=actor, reason=reason, event="auction.cancelled")
    if auction.winner_order_id:
        order = Order.objects.get(pk=auction.winner_order_id)
        if not order.is_final:
            order_services.cancel_by_platform(order, actor=actor, reason=f"إلغاء المزاد: {reason}")
    listing_services.close_auction_listing(auction.listing, status=ListingStatus.WITHDRAWN)
    return auction


# --- bidding (BR-505…510) -------------------------------------------------------------------------------
@dataclass
class BidResult:
    bid: Bid
    auction: Auction
    replayed: bool = False


def _reject(reason: str, auction: Auction, message: str) -> BidRejected:
    return BidRejected(
        message,
        details={
            "reason": reason,
            "minimum_next_bid": str(auction.minimum_next_bid),
            "current_price": str(auction.current_price) if auction.current_price is not None else None,
            "seq": auction.version,
        },
    )


def place_bid(*, auction: Auction, user, amount: Decimal, idempotency_key: str, ip: str | None = None) -> BidResult:
    if not user.is_active or user.is_staff:
        raise PermissionDeniedError("المزايدة متاحة لحسابات العملاء فقط.")
    previous = Bid.objects.filter(user=user, idempotency_key=idempotency_key).select_related("auction").first()
    if previous is not None:  # BR-507a: a retry returns the first result
        return BidResult(bid=previous, auction=previous.auction, replayed=True)

    try:
        with transaction.atomic():
            auction = _lock(auction)
            now = db_now()
            if auction.status in (AuctionStatus.DRAFT, AuctionStatus.CANCELLED):
                raise _reject("not_open", auction, "هذا المزاد غير مفتوح للمزايدة.")
            if now < auction.starts_at:
                raise _reject("not_started", auction, "لم يبدأ المزاد بعد.")
            if now >= auction.ends_at:
                raise _reject("ended", auction, "انتهى المزاد.")
            amount = Decimal(amount).quantize(Decimal("0.01"))
            if auction.highest_bid_id and auction.highest_bid.user_id == user.pk:  # BR-508
                raise _reject("already_highest", auction, "أنت المزايد الأعلى حالياً.")
            if amount < auction.minimum_next_bid:
                raise _reject("too_low", auction, f"المزايدة يجب ألا تقل عن {auction.minimum_next_bid} USD.")

            if auction.status == AuctionStatus.SCHEDULED:  # started but the tick has not run yet
                auction.status = AuctionStatus.LIVE
                AuctionStatusHistory.objects.create(auction=auction, from_status="scheduled", to_status="live")

            alias = auction.bids.filter(user=user).values_list("bidder_alias", flat=True).first()
            if alias is None:
                alias = (auction.bids.aggregate(m=Max("bidder_alias"))["m"] or 0) + 1

            previous_top = auction.highest_bid
            if previous_top is not None:
                previous_top.status = BidStatus.OUTBID
                previous_top.save(update_fields=["status"])

            extended = False
            window = timedelta(seconds=auction.extension_window_sec)
            if auction.ends_at - now <= window and auction.extensions_count < auction.max_extensions:  # BR-510
                auction.ends_at = auction.ends_at + timedelta(seconds=auction.extension_duration_sec)
                auction.extensions_count += 1
                extended = True

            seq = _bump(auction)
            bid = Bid.objects.create(
                auction=auction,
                user=user,
                amount=amount,
                bidder_alias=alias,
                idempotency_key=idempotency_key,
                auction_version=seq,
                created_at=now,
                ip=ip,
            )
            auction.highest_bid = bid
            auction.current_price = amount
            auction.bid_count += 1
            auction.save()

            _emit(
                auction,
                "bid.placed",
                bid={"id": str(bid.public_id), "amount": str(amount), "alias": alias, "created_at": now.isoformat()},
                extended=extended,
            )
            if previous_top is not None and previous_top.user_id != user.pk:
                publish_on_commit(
                    BidderNotice(
                        user_id=previous_top.user_id,
                        type="auction.outbid",
                        data={
                            "auction": str(auction.public_id),
                            "title": auction.title,
                            "current_price": str(amount),
                            "minimum_next_bid": str(auction.minimum_next_bid),
                        },
                    )
                )
            return BidResult(bid=bid, auction=auction)
    except IntegrityError:
        # A concurrent retry with the same key won the race: return its result.
        previous = Bid.objects.filter(user=user, idempotency_key=idempotency_key).select_related("auction").first()
        if previous is None:
            raise
        return BidResult(bid=previous, auction=previous.auction, replayed=True)


@transaction.atomic
def void_bid(bid: Bid, *, actor, reason: str) -> Auction:
    """BR-509: a documented administrative void while the auction is open. The bid is kept
    (never deleted); if it led, the lead returns to the best remaining bid. Extensions it
    caused are not reverted (the end time is public). After the end, the remedy is
    cancelling the auction (BR-517)."""
    reason = reason.strip()
    if not reason:
        raise _invalid("reason", "سبب إلغاء المزايدة مطلوب.")
    auction = _lock(bid.auction)
    bid = Bid.objects.select_for_update().select_related("user").get(pk=bid.pk)
    if bid.status == BidStatus.VOIDED:
        raise AuctionStateError("هذه المزايدة ملغاة بالفعل.")
    now = db_now()
    if auction.status not in (AuctionStatus.SCHEDULED, AuctionStatus.LIVE) or not (
        auction.starts_at <= now < auction.ends_at
    ):
        raise AuctionStateError("تُلغى المزايدات أثناء المزاد فقط. بعد انتهائه يُعالج الأمر بإلغاء المزاد.")

    was_top = auction.highest_bid_id == bid.pk
    bid.status = BidStatus.VOIDED
    bid.void_reason = reason
    bid.save(update_fields=["status", "void_reason"])
    auction.bid_count = max(0, auction.bid_count - 1)
    restored = None
    if was_top:
        top = (
            auction.bids.filter(status__in=[BidStatus.VALID, BidStatus.OUTBID])
            .select_related("user")
            .order_by("-amount", "created_at")
            .first()
        )
        if top is not None:
            top.status = BidStatus.VALID
            top.save(update_fields=["status"])
        auction.highest_bid = top
        auction.current_price = top.amount if top else None
        restored = top if top is not None and top.user_id != bid.user_id else None
    _bump(auction)
    auction.save()
    audit.record(
        actor=actor,
        action="auction.bid_voided",
        entity=auction,
        changes={"bid": str(bid.public_id), "amount": str(bid.amount), "was_top": was_top},
        reason=reason,
    )
    _emit(auction, "bid.voided", voided_bid=str(bid.public_id))
    base = {"auction": str(auction.public_id), "title": auction.title}
    publish_on_commit(
        BidderNotice(
            user_id=bid.user_id, type="auction.bid_voided", data={**base, "amount": str(bid.amount), "reason": reason}
        )
    )
    if restored is not None:
        publish_on_commit(
            BidderNotice(
                user_id=restored.user_id,
                type="auction.lead_restored",
                data={**base, "current_price": str(restored.amount)},
            )
        )
    return auction


# --- time transitions and resolution (BR-505, 511…514) ----------------------------------------------
def _declare_winner(auction: Auction, bid: Bid, now) -> None:
    deadline = now + timedelta(seconds=auction.winner_payment_window_sec)
    order = order_services.create_auction_order(
        user=bid.user,
        listing_id=auction.listing_id,
        amount=bid.amount,
        deposit_percent=auction.winner_deposit_percent,
        deadline=deadline,
    )
    bid.status = BidStatus.WINNING
    bid.save(update_fields=["status"])
    auction.current_winner_bid = bid
    auction.winner_declared_at = now
    auction.payment_deadline = deadline
    auction.winner_order_id = order.pk
    publish_on_commit(
        BidderNotice(
            user_id=bid.user_id,
            type="auction.won",
            data={
                "auction": str(auction.public_id),
                "title": auction.title,
                "amount": str(bid.amount),
                "order": order.order_number,
                "deposit_due": str(order.deposit_due),
                "payment_deadline": deadline.isoformat(),
            },
        )
    )


def _close(auction: Auction, now) -> None:
    """LIVE → ENDED | PENDING_WINNER_PAYMENT, in the auction's transaction."""
    top = auction.highest_bid
    if top is None:
        auction.outcome = AuctionOutcome.NO_SALE
    elif auction.reserve_price is not None and top.amount < auction.reserve_price:
        auction.outcome = AuctionOutcome.RESERVE_NOT_MET
    if auction.outcome:
        listing_services.close_auction_listing(auction.listing)
        _transition(auction, AuctionStatus.ENDED, event="auction.ended")
        return
    _declare_winner(auction, top, now)
    listing_services.close_auction_listing(auction.listing)
    _transition(
        auction,
        AuctionStatus.PENDING_WINNER_PAYMENT,
        event="auction.ended",
        winner_alias=top.bidder_alias,
        payment_deadline=auction.payment_deadline.isoformat(),
    )


def _next_bidder(auction: Auction) -> Bid | None:
    """Highest valid bid of a different, still eligible user (BR-514)."""
    excluded = auction.bids.filter(status__in=[BidStatus.NON_PAYMENT, BidStatus.WINNING]).values_list(
        "user_id", flat=True
    )
    bid = (
        auction.bids.filter(status__in=[BidStatus.VALID, BidStatus.OUTBID])
        .exclude(user_id__in=excluded)
        .order_by("-amount", "created_at")
        .first()
    )
    if bid is None or (auction.reserve_price is not None and bid.amount < auction.reserve_price):
        return None
    return bid


UNPAID_ORDER_STATUSES = (OrderStatus.EXPIRED, OrderStatus.CANCELLED_BY_CUSTOMER, OrderStatus.CANCELLED_BY_PLATFORM)


def _handle_unpaid(auction: Auction, now) -> None:
    loser = auction.current_winner_bid
    loser.status = BidStatus.NON_PAYMENT
    loser.save(update_fields=["status"])
    publish_on_commit(
        BidderNotice(
            user_id=loser.user_id,
            type="auction.award_lost",
            data={"auction": str(auction.public_id), "title": auction.title},
        )
    )
    candidate = _next_bidder(auction) if auction.non_payment_policy == NonPaymentPolicy.OFFER_NEXT_BIDDER else None
    if candidate is None:
        auction.outcome = AuctionOutcome.UNPAID
        auction.current_winner_bid = None
        _transition(auction, AuctionStatus.ENDED, reason="لم يُدفع عربون الفائز خلال المهلة.", event="auction.ended")
        return
    auction.current_price = candidate.amount
    _declare_winner(auction, candidate, now)
    _bump(auction)
    auction.save()
    AuctionStatusHistory.objects.create(
        auction=auction, from_status=auction.status, to_status=auction.status, reason="عرض على المزايد التالي"
    )
    _emit(
        auction,
        "auction.winner_changed",
        winner_alias=candidate.bidder_alias,
        payment_deadline=auction.payment_deadline.isoformat(),
    )


def advance(auction: Auction, now=None) -> bool:
    """Apply every due time transition to one auction. Returns True if it changed."""
    with transaction.atomic():
        auction = _lock(auction)
        now = now or db_now()
        changed = False
        if auction.status == AuctionStatus.SCHEDULED and now >= auction.starts_at:
            _transition(auction, AuctionStatus.LIVE, event="auction.started")
            changed = True
        if auction.status == AuctionStatus.LIVE and now >= auction.ends_at:
            _close(auction, now)
            changed = True
        if auction.status == AuctionStatus.PENDING_WINNER_PAYMENT and auction.winner_order_id:
            order = Order.objects.select_for_update().get(pk=auction.winner_order_id)
            if order.status == OrderStatus.PENDING_DEPOSIT and order.reservation_expires_at <= now:
                # Fires order_status_changed → on_order_status_changed resolves the award.
                changed = order_services.expire_if_due(order, now)
            elif order.status in UNPAID_ORDER_STATUSES:
                _handle_unpaid(auction, now)  # safety net for an award left pending
                changed = True
        return changed


def tick() -> int:
    """Beat task body (every 5 s)."""
    now = timezone.now()
    due = (
        Auction.objects.filter(status=AuctionStatus.SCHEDULED, starts_at__lte=now)
        | Auction.objects.filter(status=AuctionStatus.LIVE, ends_at__lte=now)
        | Auction.objects.filter(status=AuctionStatus.PENDING_WINNER_PAYMENT, payment_deadline__lte=now)
    )
    count = 0
    for auction in due.distinct():
        count += advance(auction)
    return count


def refresh(auction: Auction) -> Auction:
    """Lazy transition before a read, so no page ever shows a stale state."""
    now = timezone.now()
    due = (
        (auction.status == AuctionStatus.SCHEDULED and auction.starts_at <= now)
        or (auction.status == AuctionStatus.LIVE and auction.ends_at <= now)
        or (
            auction.status == AuctionStatus.PENDING_WINNER_PAYMENT
            and auction.payment_deadline
            and auction.payment_deadline <= now
        )
    )
    if due:
        advance(auction)
        auction.refresh_from_db()
    return auction


def on_order_status_changed(order: Order, to_status: str) -> None:
    """Runs inside the order's transaction.
    BR-513: the winner's confirmed deposit makes the award final.
    BR-514: an expired or cancelled winner order is a non-payment, resolved immediately."""
    if order.source != "auction" or to_status not in (OrderStatus.DEPOSIT_CONFIRMED, *UNPAID_ORDER_STATUSES):
        return
    auction = Auction.objects.filter(winner_order_id=order.pk, status=AuctionStatus.PENDING_WINNER_PAYMENT).first()
    if auction is None:
        return
    auction = _lock(auction)
    if auction.status != AuctionStatus.PENDING_WINNER_PAYMENT or auction.winner_order_id != order.pk:
        return
    if to_status == OrderStatus.DEPOSIT_CONFIRMED:
        auction.outcome = AuctionOutcome.SOLD
        _transition(auction, AuctionStatus.AWARDED, reason="تأكيد عربون الفائز", event="auction.awarded")
    else:
        _handle_unpaid(auction, db_now())


def listing_for_storefront(listing: Listing) -> Auction | None:
    return getattr(listing, "auction", None)

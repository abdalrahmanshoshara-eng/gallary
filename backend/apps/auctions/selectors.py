"""
Read paths for auctions: public lists by time window, the realtime snapshot, and the
bidder's own view. Lists classify by time (not `status`) so a late tick never shows an
ended auction as live.
"""

from __future__ import annotations

from django.db.models import Max, Prefetch, Q, QuerySet
from django.utils import timezone

from apps.artworks.models import ArtworkImage

from . import services
from .models import Auction, AuctionStatus, Bid, BidStatus

PUBLIC_STATUSES = (
    AuctionStatus.SCHEDULED,
    AuctionStatus.LIVE,
    AuctionStatus.ENDED,
    AuctionStatus.PENDING_WINNER_PAYMENT,
    AuctionStatus.AWARDED,
    AuctionStatus.CANCELLED,
)
OPEN_STATUSES = (AuctionStatus.SCHEDULED, AuctionStatus.LIVE)
SNAPSHOT_BIDS = 20


def _with_cards(qs: QuerySet[Auction]) -> QuerySet[Auction]:
    primary = ArtworkImage.objects.filter(is_primary=True).select_related("asset")
    return qs.select_related("listing__artwork__artist").prefetch_related(
        Prefetch("listing__artwork__images", queryset=primary, to_attr="primary_images")
    )


def public_auctions(window: str) -> QuerySet[Auction]:
    now = timezone.now()
    qs = Auction.objects.filter(status__in=PUBLIC_STATUSES)
    if window == "upcoming":
        qs = qs.filter(status=AuctionStatus.SCHEDULED, starts_at__gt=now).order_by("starts_at")
    elif window == "ended":
        qs = qs.filter(~Q(status__in=OPEN_STATUSES) | Q(ends_at__lte=now)).order_by("-ends_at")
    else:  # live: ending soonest first
        qs = qs.filter(status__in=OPEN_STATUSES, starts_at__lte=now, ends_at__gt=now).order_by("ends_at")
    return _with_cards(qs)


def public_auction(public_id) -> Auction:
    primary_first = ArtworkImage.objects.select_related("asset").order_by("-is_primary", "sort_order")
    return (
        Auction.objects.filter(status__in=PUBLIC_STATUSES)
        .select_related("listing__artwork__artist", "highest_bid", "current_winner_bid")
        .prefetch_related(Prefetch("listing__artwork__images", queryset=primary_first))
        .get(public_id=public_id)
    )


def is_open_now(auction: Auction, now=None) -> bool:
    now = now or timezone.now()
    return auction.status in OPEN_STATUSES and auction.starts_at <= now < auction.ends_at


def _winner_bid(auction: Auction) -> Bid | None:
    if auction.status in (AuctionStatus.PENDING_WINNER_PAYMENT, AuctionStatus.AWARDED):
        return auction.current_winner_bid
    return None


def _bid_row(bid: Bid) -> dict:
    return {"id": bid.public_id, "amount": bid.amount, "alias": bid.bidder_alias, "created_at": bid.created_at}


def snapshot(auction: Auction) -> dict:
    """Everything a viewer renders, identical for the WebSocket snapshot and REST resync."""
    winner = _winner_bid(auction)
    bids = list(auction.bids.exclude(status=BidStatus.VOIDED).order_by("-amount", "-created_at")[:SNAPSHOT_BIDS])
    return {
        "seq": auction.version,
        "server_time": timezone.now(),
        "status": auction.status,
        "outcome": auction.outcome,
        "current_price": auction.current_price,
        "minimum_next_bid": auction.minimum_next_bid,
        "bid_count": auction.bid_count,
        "starts_at": auction.starts_at,
        "ends_at": auction.ends_at,
        "extensions_count": auction.extensions_count,
        "reserve_met": services.reserve_met(auction),
        "payment_deadline": auction.payment_deadline if winner else None,
        "winner_alias": winner.bidder_alias if winner else None,
        "bids": [_bid_row(b) for b in bids],
    }


def my_state(auction: Auction, user) -> dict | None:
    """The viewer's own position. None for visitors; staff get can_bid=False."""
    if not getattr(user, "is_authenticated", False):
        return None
    mine = auction.bids.filter(user=user).exclude(status=BidStatus.VOIDED)
    top = mine.aggregate(m=Max("amount"))["m"]
    alias = mine.values_list("bidder_alias", flat=True).first()
    highest = auction.highest_bid
    is_highest = highest is not None and highest.user_id == user.pk
    winner = _winner_bid(auction)
    is_winner = winner is not None and winner.user_id == user.pk
    order_number = None
    if is_winner and auction.winner_order_id:
        from apps.orders.models import Order

        order_number = Order.objects.filter(pk=auction.winner_order_id).values_list("order_number", flat=True).first()
    return {
        "alias": alias,
        "my_top_bid": top,
        "is_highest": is_highest,
        "is_winner": is_winner,
        "order_number": order_number,
        "can_bid": bool(user.is_active and not user.is_staff and is_open_now(auction) and not is_highest),
    }


def state(auction: Auction, user) -> dict:
    return {**snapshot(auction), "me": my_state(auction, user)}


def my_bid_auctions(user) -> list[Auction]:
    """Auctions the user bid on, each annotated with their top bid and position."""
    ids = Bid.objects.filter(user=user).exclude(status=BidStatus.VOIDED).values("auction_id")
    auctions = list(
        _with_cards(Auction.objects.filter(pk__in=ids))
        .select_related("highest_bid", "current_winner_bid")
        .order_by("-ends_at")
    )
    tops = dict(
        Bid.objects.filter(user=user, auction__in=auctions)
        .exclude(status=BidStatus.VOIDED)
        .values_list("auction_id")
        .annotate(m=Max("amount"))
    )
    defaulted = set(
        Bid.objects.filter(user=user, auction__in=auctions, status=BidStatus.NON_PAYMENT).values_list(
            "auction_id", flat=True
        )
    )
    orders = _order_numbers(a.winner_order_id for a in auctions if a.winner_order_id)
    now = timezone.now()
    for a in auctions:
        a.my_top_bid = tops.get(a.pk)
        a.order_number = None
        winner = _winner_bid(a)
        if a.status == AuctionStatus.CANCELLED:
            a.my_status = "cancelled"
        elif is_open_now(a, now) or (a.status in OPEN_STATUSES and a.ends_at > now):
            a.my_status = "highest" if a.highest_bid and a.highest_bid.user_id == user.pk else "outbid"
        elif a.status in OPEN_STATUSES:
            a.my_status = "closing"  # ended by time, resolution pending the next tick
        elif winner is not None and winner.user_id == user.pk:
            a.my_status = "won" if a.status == AuctionStatus.AWARDED else "pending_payment"
            a.order_number = orders.get(a.winner_order_id)
        elif a.pk in defaulted:
            a.my_status = "unpaid"
        else:
            a.my_status = "lost"
    # Actionable first: pending payment, then live positions, then the rest by recency.
    rank = {"pending_payment": 0, "outbid": 1, "highest": 2, "closing": 3}
    auctions.sort(key=lambda a: rank.get(a.my_status, 9))
    return auctions


def _order_numbers(pks) -> dict:
    from apps.orders.models import Order

    return dict(Order.objects.filter(pk__in=list(pks)).values_list("pk", "order_number"))

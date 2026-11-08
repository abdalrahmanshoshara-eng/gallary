"""
Admin dashboard (PROJECT §9.1). Read-only aggregates across the platform; each section is
computed only for the roles allowed to see it. Balances (pending deposits, settlements due)
are "now"; flows (orders, sales, commission, ended auctions) follow the chosen period.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.roles import Role, has_any_role
from apps.artworks.models import Artwork, PublicationStatus
from apps.auctions.models import Auction, AuctionRequest, AuctionStatus, RequestStatus
from apps.listings import selectors as listing_selectors
from apps.listings.models import Listing
from apps.orders.models import Order, OrderItem, OrderItemStatus, OrderStatus
from apps.settlements.models import Settlement, SettlementStatus

ZERO = Decimal("0.00")
PERIODS = {"30d": 30, "90d": 90, "all": None}
SOLD = (OrderStatus.CONFIRMED, OrderStatus.COMPLETED)
ATTENTION_LIMIT = 5


def _since(period: str):
    days = PERIODS.get(period, 30)
    return None if days is None else timezone.now() - timedelta(days=days)


def _in_period(field: str, since) -> Q:
    return Q() if since is None else Q(**{f"{field}__gte": since})


def catalog_section() -> dict:
    published = Artwork.objects.filter(publication_status=PublicationStatus.PUBLISHED, archived_at__isnull=True)
    available = Listing.objects.filter(listing_selectors.buyable_now()).values("artwork_id").distinct().count()
    return {"published_artworks": published.count(), "available_artworks": available}


def orders_section(since) -> dict:
    sold = Order.objects.filter(status__in=SOLD).filter(_in_period("confirmed_at", since))
    sales = sold.aggregate(count=Count("id"), amount=Sum("subtotal"))
    commission = OrderItem.objects.filter(order__in=sold, status=OrderItemStatus.ACTIVE).aggregate(
        amount=Sum("commission_amount_snapshot")
    )
    return {
        "orders": Order.objects.filter(_in_period("created_at", since)).count(),
        "pending_deposit": Order.objects.filter(status=OrderStatus.PENDING_DEPOSIT).count(),
        "sales_count": sales["count"],
        "sales_amount": sales["amount"] or ZERO,
        "commission_amount": commission["amount"] or ZERO,
    }


def settlements_section() -> dict:
    due = Settlement.objects.filter(status=SettlementStatus.PENDING).aggregate(
        count=Count("id"), amount=Sum("payee_amount")
    )
    return {"pending_count": due["count"], "pending_amount": due["amount"] or ZERO}


def auctions_section(since) -> dict:
    now = timezone.now()
    open_ = Auction.objects.filter(status__in=[AuctionStatus.SCHEDULED, AuctionStatus.LIVE])
    ended = Auction.objects.filter(
        status__in=[AuctionStatus.ENDED, AuctionStatus.AWARDED, AuctionStatus.PENDING_WINNER_PAYMENT]
    ).filter(_in_period("ends_at", since))
    return {
        "live": open_.filter(starts_at__lte=now, ends_at__gt=now).count(),
        "upcoming": open_.filter(starts_at__gt=now).count(),
        "ended": ended.count(),
    }


def _attention(user) -> list[dict]:
    """Things to act on now, each linking to its screen."""
    items: list[dict] = []
    now = timezone.now()
    orders_desk = has_any_role(user, [Role.OPERATIONS_STAFF, Role.SUPER_ADMIN])
    auctions_desk = has_any_role(user, [Role.AUCTION_MANAGER, Role.SUPER_ADMIN])
    if orders_desk:
        expiring = Order.objects.filter(
            status=OrderStatus.PENDING_DEPOSIT, reservation_expires_at__lte=now + timedelta(hours=3)
        ).order_by("reservation_expires_at")
        for order in expiring[:ATTENTION_LIMIT]:
            items.append(
                {
                    "kind": "order_expiring",
                    "ref": order.order_number,
                    "label": order.contact_name,
                    "at": order.reservation_expires_at,
                }
            )
        held = Settlement.objects.filter(status=SettlementStatus.ON_HOLD).count()
        if held:
            items.append({"kind": "settlements_on_hold", "ref": "", "label": "", "at": None, "count": held})
    if auctions_desk:
        for auction in Auction.objects.filter(status=AuctionStatus.PENDING_WINNER_PAYMENT).order_by("payment_deadline")[
            :ATTENTION_LIMIT
        ]:
            items.append(
                {
                    "kind": "auction_awaiting_winner",
                    "ref": str(auction.public_id),
                    "label": auction.title,
                    "at": auction.payment_deadline,
                }
            )
        new_requests = AuctionRequest.objects.filter(status=RequestStatus.SUBMITTED).count()
        if new_requests:
            items.append({"kind": "auction_requests_new", "ref": "", "label": "", "at": None, "count": new_requests})
    return items


def dashboard(user, period: str = "30d") -> dict:
    period = period if period in PERIODS else "30d"
    since = _since(period)
    catalog = has_any_role(user, [Role.CONTENT_STAFF, Role.SUPER_ADMIN])
    orders = has_any_role(user, [Role.OPERATIONS_STAFF, Role.SUPER_ADMIN])
    auctions = has_any_role(user, [Role.AUCTION_MANAGER, Role.SUPER_ADMIN])
    return {
        "period": period,
        "generated_at": timezone.now(),
        "catalog": catalog_section() if catalog else None,
        "orders": orders_section(since) if orders else None,
        "settlements": settlements_section() if orders else None,
        "auctions": auctions_section(since) if auctions else None,
        "attention": _attention(user),
    }

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auctions import services
from apps.auctions.models import Auction


@pytest.fixture
def manager(make_user):
    return make_user(roles=["auction_manager"], display_name="مدير المزادات")


@pytest.fixture
def bidders(make_user):
    return [make_user(display_name=f"مزايد {i}") for i in range(1, 5)]


@pytest.fixture
def make_auction(artwork_factory, manager):
    """A scheduled auction; `live=True` puts its window around now (bids use the DB clock,
    so tests move real timestamps instead of freezing time)."""

    def _make(*, live=True, schedule=True, minutes_left=60, artwork=None, **terms):
        now = timezone.now()
        data = {
            "starting_price": Decimal("100.00"),
            "minimum_increment": Decimal("10.00"),
            "starts_at": now - timedelta(minutes=1) if live else now + timedelta(hours=1),
            "ends_at": now + timedelta(minutes=minutes_left) if live else now + timedelta(hours=2),
            **terms,
        }
        auction = services.create_auction(actor=manager, artwork=artwork or artwork_factory(published=True), data=data)
        if schedule:
            services.schedule(auction, actor=manager)
        auction.refresh_from_db()
        return auction

    return _make


def bid(auction, user, amount, key=None):
    import uuid

    return services.place_bid(
        auction=auction, user=user, amount=Decimal(amount), idempotency_key=key or uuid.uuid4().hex
    )


def end_now(auction: Auction) -> Auction:
    """Move the end into the past and run the tick (as Beat would)."""
    Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
    services.tick()
    auction.refresh_from_db()
    return auction


def deadline_passes(auction: Auction) -> Auction:
    from apps.orders.models import Order

    past = timezone.now() - timedelta(seconds=1)
    Auction.objects.filter(pk=auction.pk).update(payment_deadline=past)
    Order.objects.filter(pk=auction.winner_order_id).update(reservation_expires_at=past)
    services.tick()
    auction.refresh_from_db()
    return auction

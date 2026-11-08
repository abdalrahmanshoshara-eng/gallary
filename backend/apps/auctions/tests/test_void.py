"""BR-509: administrative bid voids while the auction is open."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auctions.events import AuctionEvent, BidderNotice
from apps.auctions.models import Auction, BidStatus
from apps.audit.models import AuditLog
from apps.core.events import get_event_bus
from apps.orders.models import Order

from .conftest import bid, end_now

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/auctions"


def void(client, auction, b, reason="مزايدة بالخطأ بحسب اتصال العميل"):
    return client.post(f"{ADMIN}/{auction.public_id}/bids/{b.public_id}/void", {"reason": reason}, format="json")


def test_voiding_the_top_bid_restores_the_previous_leader(
    make_auction, bidders, login_client, manager, django_capture_on_commit_callbacks
):
    auction = make_auction()
    a, b = bidders[:2]
    bid(auction, a, "100")
    top = bid(auction, b, "150").bid
    version = Auction.objects.get(pk=auction.pk).version
    with django_capture_on_commit_callbacks(execute=True):
        response = void(login_client(manager), auction, top)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["current_price"] == "100.00" and body["minimum_next_bid"] == "110.00" and body["bid_count"] == 1
    voided = next(x for x in body["bids"] if x["id"] == str(top.public_id))
    assert voided["status"] == "voided" and voided["void_reason"] == "مزايدة بالخطأ بحسب اتصال العميل"
    auction.refresh_from_db()
    assert auction.highest_bid.user == a and auction.highest_bid.status == BidStatus.VALID
    assert auction.version == version + 1

    event = [e for e in get_event_bus().events if isinstance(e, AuctionEvent)][-1]
    assert event.type == "bid.voided" and event.seq == auction.version and event.data["current_price"] == "100.00"
    notices = {(e.type, e.user_id) for e in get_event_bus().events if isinstance(e, BidderNotice)}
    assert ("auction.bid_voided", b.pk) in notices and ("auction.lead_restored", a.pk) in notices
    assert AuditLog.objects.filter(action="auction.bid_voided", reason__contains="بالخطأ").exists()

    public = login_client(a).get(f"/api/v1/auctions/{auction.public_id}/state").json()
    assert [row["amount"] for row in public["bids"]] == ["100.00"]
    assert public["me"]["is_highest"] is True


def test_voiding_a_lower_bid_keeps_the_price(make_auction, bidders, login_client, manager):
    auction = make_auction()
    low = bid(auction, bidders[0], "100").bid
    bid(auction, bidders[1], "150")
    body = void(login_client(manager), auction, low).json()
    assert body["current_price"] == "150.00" and body["bid_count"] == 1


def test_voiding_the_only_bid_returns_to_the_opening_price(make_auction, bidders, login_client, manager):
    auction = make_auction()
    only = bid(auction, bidders[0], "100").bid
    body = void(login_client(manager), auction, only).json()
    assert body["current_price"] is None and body["minimum_next_bid"] == "100.00" and body["bid_count"] == 0
    # The voided bidder may bid again; a voided bid never wins.
    bid(auction, bidders[0], "100")
    end_now(auction)
    assert Order.objects.get(pk=auction.winner_order_id).subtotal == Decimal("100.00")


def test_void_rules(make_auction, bidders, login_client, manager, customer, make_user):
    auction = make_auction()
    b = bid(auction, bidders[0], "100").bid
    client = login_client(manager)
    assert void(client, auction, b, reason=" ").status_code == 400
    for user in (customer, make_user(roles=["operations_staff"])):
        assert void(login_client(user), auction, b).status_code == 403
    other = make_auction()
    assert (
        client.post(f"{ADMIN}/{other.public_id}/bids/{b.public_id}/void", {"reason": "x"}, format="json").status_code
        == 404
    )
    assert void(client, auction, b).status_code == 200
    assert void(client, auction, b).status_code == 409  # already voided

    ended = make_auction()
    late = bid(ended, bidders[1], "100").bid
    Auction.objects.filter(pk=ended.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
    assert void(client, ended, late).status_code == 409


def test_admin_detail_says_when_bids_can_be_voided(make_auction, login_client, manager):
    live = make_auction()
    upcoming = make_auction(live=False)
    client = login_client(manager)
    assert client.get(f"{ADMIN}/{live.public_id}").json()["bids_voidable"] is True
    assert client.get(f"{ADMIN}/{upcoming.public_id}").json()["bids_voidable"] is False

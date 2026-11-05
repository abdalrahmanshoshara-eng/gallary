import threading
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.auctions import services
from apps.auctions.events import AuctionEvent, BidderNotice
from apps.auctions.models import Auction, AuctionStatus, Bid, BidStatus
from apps.core.errors import PermissionDeniedError
from apps.core.events import get_event_bus

from .conftest import bid

pytestmark = pytest.mark.django_db


def bid_api(client, auction, amount, key=None):
    return client.post(
        f"/api/v1/auctions/{auction.public_id}/bids",
        {"amount": amount},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex,
    )


def reason_of(response):
    return response.json()["error"]["details"]["reason"]


# --- acceptance rules (BR-505…508) ---------------------------------------------------------------
def test_first_bid_at_starting_price_then_minimum_increment(make_auction, bidders, login_client):
    auction = make_auction()
    a, b = bidders[:2]
    first = bid_api(login_client(a), auction, "100.00")
    assert first.status_code == 201, first.json()
    body = first.json()
    assert body["bid"]["alias"] == 1 and body["replayed"] is False
    assert body["state"]["current_price"] == "100.00" and body["state"]["minimum_next_bid"] == "110.00"
    assert body["state"]["me"]["is_highest"] is True and body["state"]["me"]["can_bid"] is False

    low = bid_api(login_client(b), auction, "105.00")
    assert low.status_code == 409 and reason_of(low) == "too_low"
    assert low.json()["error"]["details"]["minimum_next_bid"] == "110.00"
    assert bid_api(login_client(b), auction, "110.00").status_code == 201
    auction.refresh_from_db()
    assert auction.current_price == Decimal("110.00") and auction.bid_count == 2 and auction.version >= 3


def test_highest_bidder_cannot_outbid_themselves(make_auction, bidders, login_client):
    auction = make_auction()
    client = login_client(bidders[0])
    bid_api(client, auction, "100.00")
    again = bid_api(client, auction, "200.00")
    assert again.status_code == 409 and reason_of(again) == "already_highest"


def test_bids_outside_the_window_are_refused_by_the_database_clock(make_auction, bidders, login_client):
    upcoming = make_auction(live=False)
    response = bid_api(login_client(bidders[0]), upcoming, "100.00")
    assert response.status_code == 409 and reason_of(response) == "not_started"

    live = make_auction()
    # The end passed but no tick ran yet: status still says LIVE, the clock decides.
    Auction.objects.filter(pk=live.pk).update(ends_at=timezone.now() - timedelta(milliseconds=5))
    late = bid_api(login_client(bidders[0]), live, "100.00")
    assert late.status_code == 409 and reason_of(late) == "ended"
    assert not Bid.objects.filter(auction=live).exists()


def test_draft_auctions_are_invisible_and_closed(make_auction, bidders, login_client, api_client):
    draft = make_auction(schedule=False)
    assert api_client.get(f"/api/v1/auctions/{draft.public_id}").status_code == 404
    assert bid_api(login_client(bidders[0]), draft, "100.00").status_code == 404


def test_scheduled_auction_starts_on_first_bid_even_before_the_tick(make_auction, bidders):
    auction = make_auction()
    assert auction.status == AuctionStatus.SCHEDULED
    bid(auction, bidders[0], "100")
    auction.refresh_from_db()
    assert auction.status == AuctionStatus.LIVE


def test_staff_visitors_and_missing_keys_cannot_bid(make_auction, manager, bidders, login_client, api_client):
    auction = make_auction()
    assert bid_api(api_client, auction, "100.00").status_code in (401, 403)
    assert bid_api(login_client(manager), auction, "100.00").status_code == 403
    with pytest.raises(PermissionDeniedError):
        bid(auction, manager, "100")
    no_key = login_client(bidders[0]).post(
        f"/api/v1/auctions/{auction.public_id}/bids", {"amount": "100"}, format="json"
    )
    assert no_key.status_code == 400 and no_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


# --- idempotency and aliases (BR-507a, 509) --------------------------------------------------------
def test_retry_with_same_key_returns_first_result_without_second_bid(make_auction, bidders, login_client):
    auction = make_auction()
    client = login_client(bidders[0])
    first = bid_api(client, auction, "100.00", key="retry-key-123")
    retry = bid_api(client, auction, "100.00", key="retry-key-123")
    assert first.status_code == 201 and retry.status_code == 200
    assert retry.json()["replayed"] is True and retry.json()["bid"]["id"] == first.json()["bid"]["id"]
    assert Bid.objects.filter(auction=auction).count() == 1


def test_aliases_are_stable_per_bidder_and_hide_identity(make_auction, bidders, login_client, api_client):
    auction = make_auction()
    a, b = bidders[:2]
    bid(auction, a, "100")
    bid(auction, b, "110")
    bid(auction, a, "120")
    aliases = list(Bid.objects.filter(auction=auction).order_by("created_at").values_list("bidder_alias", flat=True))
    assert aliases == [1, 2, 1]
    state = api_client.get(f"/api/v1/auctions/{auction.public_id}/state").json()
    assert state["me"] is None
    assert [row["alias"] for row in state["bids"]] == [1, 2, 1]
    assert all(set(row) == {"id", "amount", "alias", "created_at"} for row in state["bids"])
    mine = login_client(b).get(f"/api/v1/auctions/{auction.public_id}/state").json()["me"]
    assert mine == {
        "alias": 2,
        "my_top_bid": "110.00",
        "is_highest": False,
        "is_winner": False,
        "order_number": None,
        "can_bid": True,
    }


# --- events (ARCHITECTURE §5.4) -----------------------------------------------------------------------
def test_bid_publishes_ordered_event_and_outbid_notice(make_auction, bidders, django_capture_on_commit_callbacks):
    auction = make_auction()
    a, b = bidders[:2]
    with django_capture_on_commit_callbacks(execute=True):
        bid(auction, a, "100")
        bid(auction, b, "130")
    events = [e for e in get_event_bus().events if isinstance(e, AuctionEvent) and e.type == "bid.placed"]
    assert [e.data["current_price"] for e in events] == ["100.00", "130.00"]
    assert events[1].seq == events[0].seq + 1
    notices = [e for e in get_event_bus().events if isinstance(e, BidderNotice)]
    assert len(notices) == 1 and notices[0].user_id == a.pk and notices[0].type == "auction.outbid"
    assert notices[0].data["minimum_next_bid"] == "140.00"
    assert Bid.objects.get(user=a).status == BidStatus.OUTBID


# --- anti-sniping (BR-510) ------------------------------------------------------------------------------
def test_bid_in_last_window_extends_until_the_cap(make_auction, bidders):
    auction = make_auction(minutes_left=2, max_extensions=2)
    original = auction.ends_at
    a, b = bidders[:2]
    bid(auction, a, "100")
    auction.refresh_from_db()
    assert auction.extensions_count == 1 and auction.ends_at == original + timedelta(minutes=5)
    assert auction.original_ends_at == original
    # 7 minutes left now: outside the window, no extension.
    bid(auction, b, "110")
    auction.refresh_from_db()
    assert auction.extensions_count == 1
    Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() + timedelta(minutes=1))
    bid(auction, a, "120")
    Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() + timedelta(minutes=1))
    bid(auction, b, "130")
    auction.refresh_from_db()
    assert auction.extensions_count == 2  # capped


# --- concurrency (BR-506) ------------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_simultaneous_bids_at_the_same_amount_accept_exactly_one(make_auction, bidders):
    auction = make_auction()
    results, barrier = [], threading.Barrier(3)

    def attempt(user):
        barrier.wait()
        try:
            bid(auction, user, "100")
            results.append("ok")
        except services.BidRejected as error:
            results.append(error.details["reason"])
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(u,)) for u in bidders[:3]]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "too_low", "too_low"]
    auction.refresh_from_db()
    assert auction.bid_count == 1 and auction.current_price == Decimal("100.00")


# --- bidder views -----------------------------------------------------------------------------------------
def test_my_bids_lists_positions_with_actionable_first(make_auction, bidders, login_client):
    first, second = make_auction(), make_auction()
    a, b = bidders[:2]
    bid(first, a, "100")
    bid(second, a, "100")
    bid(second, b, "110")
    rows = login_client(a).get("/api/v1/me/bids").json()
    assert [(r["id"], r["my_status"]) for r in rows] == [
        (str(second.public_id), "outbid"),
        (str(first.public_id), "highest"),
    ]
    assert rows[0]["my_top_bid"] == "100.00"


def test_public_lists_classify_by_time(make_auction, api_client):
    live = make_auction()
    upcoming = make_auction(live=False)
    ended = make_auction()
    Auction.objects.filter(pk=ended.pk).update(ends_at=timezone.now() - timedelta(seconds=1))  # tick not run yet

    def ids(window):
        return [r["id"] for r in api_client.get(f"/api/v1/auctions?status={window}").json()["results"]]

    assert ids("live") == [str(live.public_id)]
    assert ids("upcoming") == [str(upcoming.public_id)]
    assert ids("ended") == [str(ended.public_id)]


def test_storefront_offer_links_to_the_auction(make_auction, api_client):
    auction = make_auction()
    slug = auction.listing.artwork.slug
    offer = api_client.get(f"/api/v1/artworks/{slug}").json()["offer"]
    assert offer["sale_mode"] == "auction" and offer["auction_id"] == str(auction.public_id)
    assert offer["purchasable"] is False

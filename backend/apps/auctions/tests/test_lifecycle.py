from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.auctions import services
from apps.auctions.events import AuctionEvent, BidderNotice
from apps.auctions.models import Auction, AuctionOutcome, AuctionStatus, BidStatus
from apps.core.errors import ConflictError
from apps.core.events import get_event_bus
from apps.listings.models import ListingStatus
from apps.orders import services as order_services
from apps.orders.models import Order, OrderStatus

from .conftest import bid, deadline_passes, end_now

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/auctions"


def confirm_deposit(order, actor, amount=None):
    return order_services.record_payment(
        order, actor=actor, kind="deposit", amount=Decimal(amount or order.deposit_due), method="cash"
    )


# --- creation and scheduling (BR-501…504) -------------------------------------------------------
def test_manager_creates_draft_then_schedules_through_api(login_client, manager, artwork_factory):
    artwork = artwork_factory(published=True)
    client = login_client(manager)
    now = timezone.now()
    created = client.post(
        ADMIN,
        {
            "artwork": str(artwork.public_id),
            "starting_price": "500.00",
            "minimum_increment": "25.00",
            "reserve_price": "800.00",
            "starts_at": (now + timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "winner_deposit_percent": "60",
        },
        format="json",
    )
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["status"] == "draft" and body["editable"] is True and body["schedule_problems"] == []
    assert body["title"] == artwork.title and body["reserve_price"] == "800.00"
    scheduled = client.post(f"{ADMIN}/{body['id']}/schedule")
    assert scheduled.status_code == 200 and scheduled.json()["status"] == "scheduled"
    auction = Auction.objects.get(public_id=body["id"])
    assert auction.listing.status == ListingStatus.ACTIVE and auction.listing.sale_mode == "auction"
    # Public detail never reveals the reserve itself.
    public = login_client(manager).get(f"/api/v1/auctions/{body['id']}").json()
    assert "reserve_price" not in public and public["reserve_met"] is False


def test_terms_are_validated(login_client, manager, artwork_factory):
    artwork = artwork_factory(published=True)
    now = timezone.now()
    base = {
        "artwork": str(artwork.public_id),
        "starting_price": "500.00",
        "minimum_increment": "25.00",
        "starts_at": now.isoformat(),
        "ends_at": (now + timedelta(hours=1)).isoformat(),
    }
    client = login_client(manager)
    for override, field in (
        ({"ends_at": now.isoformat()}, "ends_at"),
        ({"reserve_price": "100.00"}, "reserve_price"),
        ({"winner_deposit_percent": "40"}, "winner_deposit_percent"),
    ):
        response = client.post(ADMIN, {**base, **override}, format="json")
        assert response.status_code == 400 and field in response.json()["error"]["details"], override


def test_one_open_offer_per_artwork(make_auction, manager, listing_factory, artwork_factory):
    artwork = artwork_factory(published=True)
    listing_factory(artwork)
    with pytest.raises(ConflictError):
        make_auction(artwork=artwork)
    auction = make_auction()
    with pytest.raises(ConflictError):
        make_auction(artwork=auction.listing.artwork)


def test_unpublished_artwork_cannot_be_scheduled(make_auction, artwork_factory, login_client, manager):
    auction = make_auction(schedule=False, artwork=artwork_factory())
    response = login_client(manager).post(f"{ADMIN}/{auction.public_id}/schedule")
    assert response.status_code == 409 and response.json()["error"]["details"]["problems"] == ["artwork_not_public"]


def test_terms_freeze_once_started(make_auction, login_client, manager):
    auction = make_auction()
    response = login_client(manager).patch(f"{ADMIN}/{auction.public_id}", {"minimum_increment": "50"}, format="json")
    assert response.status_code == 409
    upcoming = make_auction(live=False)
    ok = login_client(manager).patch(f"{ADMIN}/{upcoming.public_id}", {"minimum_increment": "50"}, format="json")
    assert ok.status_code == 200 and ok.json()["minimum_increment"] == "50.00"


def test_auction_staff_only(make_auction, login_client, customer, make_user):
    auction = make_auction()
    for user in (customer, make_user(roles=["operations_staff"]), make_user(roles=["content_staff"])):
        assert login_client(user).get(f"{ADMIN}/{auction.public_id}").status_code == 403
        assert login_client(user).get(ADMIN).status_code == 403


# --- time transitions (BR-505, 511) ---------------------------------------------------------------
def test_tick_starts_and_ends_with_no_sale(make_auction, django_capture_on_commit_callbacks):
    auction = make_auction()
    with django_capture_on_commit_callbacks(execute=True):
        services.tick()
    auction.refresh_from_db()
    assert auction.status == AuctionStatus.LIVE
    with django_capture_on_commit_callbacks(execute=True):
        end_now(auction)
    assert auction.status == AuctionStatus.ENDED and auction.outcome == AuctionOutcome.NO_SALE
    assert auction.listing.status == ListingStatus.ENDED
    types = [e.type for e in get_event_bus().events if isinstance(e, AuctionEvent)]
    assert types[-2:] == ["auction.started", "auction.ended"]


def test_reserve_not_met_has_no_winner(make_auction, bidders):
    auction = make_auction(reserve_price=Decimal("500.00"))
    bid(auction, bidders[0], "100")
    end_now(auction)
    assert auction.outcome == AuctionOutcome.RESERVE_NOT_MET and auction.winner_order_id is None
    assert not Order.objects.exists()


def test_reading_an_overdue_auction_resolves_it_lazily(make_auction, bidders, api_client):
    auction = make_auction()
    bid(auction, bidders[0], "100")
    Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
    state = api_client.get(f"/api/v1/auctions/{auction.public_id}/state").json()
    assert state["status"] == "pending_winner_payment" and state["winner_alias"] == 1


# --- winner, payment and award (BR-511…513, 410) -------------------------------------------------------
def test_winner_gets_auction_order_with_deposit_and_one_hour(
    make_auction, bidders, login_client, django_capture_on_commit_callbacks
):
    auction = make_auction(winner_deposit_percent=Decimal("60"))
    a, b = bidders[:2]
    bid(auction, a, "100")
    bid(auction, b, "250")
    with django_capture_on_commit_callbacks(execute=True):
        end_now(auction)
    assert auction.status == AuctionStatus.PENDING_WINNER_PAYMENT
    order = Order.objects.get(pk=auction.winner_order_id)
    assert order.user == b and order.source == "auction" and order.status == OrderStatus.PENDING_DEPOSIT
    assert order.subtotal == Decimal("250.00") and order.deposit_due == Decimal("150.00")
    window = order.reservation_expires_at - auction.winner_declared_at
    assert timedelta(minutes=59) < window <= timedelta(hours=1)
    won = [e for e in get_event_bus().events if isinstance(e, BidderNotice) and e.type == "auction.won"]
    assert won[0].user_id == b.pk and won[0].data["order"] == order.order_number

    me = login_client(b).get(f"/api/v1/auctions/{auction.public_id}/state").json()["me"]
    assert me["is_winner"] is True and me["order_number"] == order.order_number
    detail = login_client(b).get(f"/api/v1/orders/{order.order_number}").json()
    assert detail["source"] == "auction" and detail["can_cancel"] is False
    loser = login_client(a).get(f"/api/v1/auctions/{auction.public_id}/state").json()["me"]
    assert loser["is_winner"] is False and loser["order_number"] is None
    rows = login_client(a).get("/api/v1/me/bids").json()
    assert rows[0]["my_status"] == "lost"


def test_confirmed_deposit_awards_the_auction(make_auction, bidders, make_user):
    ops = make_user(roles=["operations_staff"])
    auction = make_auction()
    bid(auction, bidders[0], "300")
    end_now(auction)
    order = Order.objects.get(pk=auction.winner_order_id)
    confirm_deposit(order, ops)
    auction.refresh_from_db()
    order.refresh_from_db()
    assert auction.status == AuctionStatus.AWARDED and auction.outcome == AuctionOutcome.SOLD
    assert order.status == OrderStatus.DEPOSIT_CONFIRMED


def test_winner_cannot_cancel_and_deposit_floor_is_fifty_percent(make_auction, bidders, super_admin):
    auction = make_auction()
    bid(auction, bidders[0], "300")
    end_now(auction)
    order = Order.objects.get(pk=auction.winner_order_id)
    with pytest.raises(ConflictError):
        order_services.cancel_by_customer(order, user=bidders[0])
    with pytest.raises(ConflictError):
        order_services.set_custom_deposit(order, actor=super_admin, amount=Decimal("100"), reason="خفض")


def test_auction_manager_sees_only_auction_orders(make_auction, bidders, login_client, manager):
    auction = make_auction()
    bid(auction, bidders[0], "300")
    end_now(auction)
    client = login_client(manager)
    numbers = [r["number"] for r in client.get("/api/v1/admin/orders").json()["results"]]
    order = Order.objects.get(pk=auction.winner_order_id)
    assert numbers == [order.order_number]
    assert client.get(f"/api/v1/admin/orders/{order.order_number}").status_code == 200


# --- non-payment (BR-514) --------------------------------------------------------------------------------
def test_unpaid_winner_offers_the_next_bidder(make_auction, bidders, django_capture_on_commit_callbacks):
    auction = make_auction()
    a, b, c = bidders[:3]
    bid(auction, a, "100")
    bid(auction, b, "110")
    bid(auction, a, "120")
    bid(auction, c, "130")
    end_now(auction)
    first_order = Order.objects.get(pk=auction.winner_order_id)
    with django_capture_on_commit_callbacks(execute=True):
        deadline_passes(auction)
    first_order.refresh_from_db()
    assert first_order.status == OrderStatus.EXPIRED
    assert auction.status == AuctionStatus.PENDING_WINNER_PAYMENT
    second = Order.objects.get(pk=auction.winner_order_id)
    assert second.user == a and second.subtotal == Decimal("120.00")  # a's best bid, not a new price
    assert auction.current_price == Decimal("120.00")
    assert auction.bids.get(user=c).status == BidStatus.NON_PAYMENT
    notices = {(e.type, e.user_id) for e in get_event_bus().events if isinstance(e, BidderNotice)}
    assert ("auction.award_lost", c.pk) in notices and ("auction.won", a.pk) in notices
    # The defaulting bidder is never offered the auction again.
    deadline_passes(auction)
    third = Order.objects.get(pk=auction.winner_order_id)
    assert third.user == b


def test_cancel_award_policy_ends_without_sale(make_auction, bidders):
    auction = make_auction(non_payment_policy="cancel_award")
    bid(auction, bidders[0], "100")
    bid(auction, bidders[1], "110")
    end_now(auction)
    deadline_passes(auction)
    assert auction.status == AuctionStatus.ENDED and auction.outcome == AuctionOutcome.UNPAID


def test_order_expiry_task_also_resolves_the_award(make_auction, bidders):
    auction = make_auction(non_payment_policy="cancel_award")
    bid(auction, bidders[0], "100")
    end_now(auction)
    Order.objects.filter(pk=auction.winner_order_id).update(
        reservation_expires_at=timezone.now() - timedelta(seconds=1)
    )
    order_services.expire_due_orders()
    auction.refresh_from_db()
    assert auction.status == AuctionStatus.ENDED and auction.outcome == AuctionOutcome.UNPAID


# --- cancellation (BR-517) ---------------------------------------------------------------------------------
def test_cancel_requires_reason_and_cancels_winner_order_without_reoffering(
    make_auction, bidders, login_client, manager, make_user
):
    auction = make_auction()
    bid(auction, bidders[0], "100")
    bid(auction, bidders[1], "110")
    end_now(auction)
    order = Order.objects.get(pk=auction.winner_order_id)
    confirm_deposit(order, make_user(roles=["operations_staff"]), amount=order.deposit_due - 1)  # partial
    client = login_client(manager)
    assert client.post(f"{ADMIN}/{auction.public_id}/cancel", {"reason": " "}, format="json").status_code == 400
    response = client.post(f"{ADMIN}/{auction.public_id}/cancel", {"reason": "خطأ في وصف العمل"}, format="json")
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED_BY_PLATFORM and order.deposit_status == "refund_due"
    auction.refresh_from_db()
    assert auction.current_winner_bid.user == bidders[1]  # not re-offered to the next bidder
    assert Order.objects.count() == 1
    assert client.post(f"{ADMIN}/{auction.public_id}/cancel", {"reason": "مرة أخرى"}, format="json").status_code == 409


def test_artwork_picker_lists_only_eligible_works(
    make_auction, artwork_factory, listing_factory, login_client, manager
):
    free = artwork_factory(published=True, title="حرّة")
    listed = artwork_factory(published=True, title="معروضة")
    listing_factory(listed)
    artwork_factory(title="مسودة")
    in_auction = make_auction().listing.artwork
    rows = login_client(manager).get(f"{ADMIN}/eligible-artworks").json()["results"]
    ids = {r["id"] for r in rows}
    assert str(free.public_id) in ids
    assert not ids & {str(listed.public_id), str(in_auction.public_id)}
    assert all(r["title"] != "مسودة" for r in rows)

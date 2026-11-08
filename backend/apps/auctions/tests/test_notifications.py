"""§26 auction and auction-request notifications."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.auctions import services
from apps.auctions.models import Auction
from apps.notifications.models import EmailStatus, Notification
from apps.orders.models import Order

from .conftest import bid, deadline_passes, end_now

pytestmark = pytest.mark.django_db


def kinds(user):
    return list(Notification.objects.filter(user=user).order_by("created_at", "id").values_list("kind", flat=True))


def test_outbid_is_in_app_only(make_auction, bidders):
    auction = make_auction()
    a, b = bidders[:2]
    bid(auction, a, "100")
    bid(auction, b, "110")
    n = Notification.objects.get(user=a)
    assert n.kind == "auction.outbid" and n.link == f"/auctions/{auction.public_id}"
    assert "110 US$" in n.body and "120 US$" in n.body
    assert n.email_status == EmailStatus.NONE
    assert not Notification.objects.filter(user=b).exists()


def test_winner_is_told_the_deposit_and_deadline_by_email(make_auction, make_user, django_capture_on_commit_callbacks):
    winner = make_user(email="win@example.com")
    auction = make_auction()
    bid(auction, winner, "500")
    with django_capture_on_commit_callbacks(execute=True):
        auction = end_now(auction)
    order = Order.objects.get(pk=auction.winner_order_id)
    n = Notification.objects.get(user=winner, kind="auction.won")
    assert n.link == f"/orders/{order.order_number}" and "500 US$" in n.body and "250 US$" in n.body
    assert order.order_number in n.body
    assert [m.to for m in mail.outbox] == [["win@example.com"]]


def test_unpaid_winner_loses_the_award_without_an_order_expiry_notice(make_auction, bidders):
    auction = make_auction()
    first, second = bidders[:2]
    bid(auction, second, "100")
    bid(auction, first, "200")
    auction = deadline_passes(end_now(auction))
    assert kinds(first) == ["auction.won", "auction.award_lost"]
    assert kinds(second)[-1] == "auction.won"  # offered to the next bidder (default policy)


def test_ending_soon_once_per_bidder_with_their_position(make_auction, bidders):
    auction = make_auction(minutes_left=60)
    a, b, idle = bidders[:3]
    bid(auction, a, "100")
    bid(auction, b, "110")
    assert services.notify_ending_soon() == 0  # an hour left
    Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() + timedelta(minutes=10))
    assert services.notify_ending_soon() == 2
    assert services.notify_ending_soon() == 0
    assert "ليست الأعلى" in Notification.objects.get(user=a, kind="auction.ending_soon").body
    assert "أنت صاحب أعلى مزايدة" in Notification.objects.get(user=b, kind="auction.ending_soon").body
    assert not Notification.objects.filter(user=idle).exists()


def test_voided_bid_explains_and_restores_the_lead(make_auction, bidders, manager):
    auction = make_auction()
    a, b = bidders[:2]
    bid(auction, a, "100")
    top = bid(auction, b, "110").bid
    services.void_bid(top, actor=manager, reason="حساب مكرر")
    voided = Notification.objects.get(user=b, kind="auction.bid_voided")
    assert "حساب مكرر" in voided.body and voided.email_status == EmailStatus.NONE  # b has no e-mail
    assert kinds(a) == ["auction.outbid", "auction.lead_restored"]

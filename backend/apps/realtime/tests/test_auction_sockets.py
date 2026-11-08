"""Auction streams (ARCHITECTURE §5.4): snapshot on connect, ordered events, private notices."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.db import connections
from django.test import Client
from django.utils import timezone

from apps.auctions import services
from apps.core.events import reset_event_bus
from apps.realtime.protocol import CLOSE_NOT_FOUND
from config.asgi import application

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
async def _close_thread_connections():
    yield
    await sync_to_async(connections.close_all)()


@pytest.fixture(autouse=True)
def channels_bus(settings):
    settings.EVENT_BUS_BACKEND = "apps.realtime.publisher.ChannelsEventBus"
    reset_event_bus()


@pytest.fixture
def live_auction(artwork_factory, make_user):
    manager = make_user(roles=["auction_manager"])
    now = timezone.now()
    auction = services.create_auction(
        actor=manager,
        artwork=artwork_factory(published=True),
        data={
            "starting_price": Decimal("100"),
            "minimum_increment": Decimal("10"),
            "starts_at": now - timedelta(minutes=1),
            "ends_at": now + timedelta(hours=1),
        },
    )
    services.schedule(auction, actor=manager)
    auction.refresh_from_db()
    return auction


def _cookie(user) -> bytes:
    client = Client()
    client.force_login(user)
    return f"{settings.SESSION_COOKIE_NAME}={client.cookies[settings.SESSION_COOKIE_NAME].value}".encode()


async def socket(path, user=None):
    headers = [(b"origin", b"http://localhost")]
    if user is not None:
        headers.append((b"cookie", await sync_to_async(_cookie)(user)))
    return WebsocketCommunicator(application, path, headers=headers)


def place(auction, user, amount):
    return services.place_bid(auction=auction, user=user, amount=Decimal(amount), idempotency_key=uuid.uuid4().hex)


async def test_snapshot_then_ordered_bid_events_for_anonymous_viewers(live_auction, make_user):
    a = await sync_to_async(make_user)()
    ws = await socket(f"/ws/auctions/{live_auction.public_id}/")
    connected, _ = await ws.connect()
    assert connected
    snapshot = await ws.receive_json_from()
    assert snapshot["type"] == "auction.snapshot"
    # The connect applied the due start lazily (SCHEDULED → LIVE bumps the version).
    assert snapshot["data"]["status"] == "live" and snapshot["seq"] == live_auction.version + 1
    assert snapshot["data"]["minimum_next_bid"] == "100.00" and snapshot["data"]["bids"] == []
    assert "me" not in snapshot["data"]

    # The lazy start's own event can arrive after the snapshot: same seq, so clients drop it.
    started = await ws.receive_json_from()
    assert started["type"] == "auction.started" and started["seq"] == snapshot["seq"]

    await sync_to_async(place)(live_auction, a, "100")
    event = await ws.receive_json_from()
    assert event["type"] == "bid.placed" and event["seq"] == snapshot["seq"] + 1
    assert event["data"]["current_price"] == "100.00" and event["data"]["bid"]["alias"] == 1
    assert "user" not in event["data"]["bid"]
    await ws.disconnect()


async def test_unknown_or_draft_auction_closes_with_404(live_auction):
    ws = await socket(f"/ws/auctions/{uuid.uuid4()}/")
    connected, _ = await ws.connect()
    assert connected  # accepted, then closed after the lookup
    message = await ws.receive_output()
    assert message == {"type": "websocket.close", "code": CLOSE_NOT_FOUND}


async def test_outbid_notice_reaches_only_the_outbid_bidder(live_auction, make_user):
    a = await sync_to_async(make_user)()
    b = await sync_to_async(make_user)()
    ws_a, ws_b = await socket("/ws/me/", a), await socket("/ws/me/", b)
    await ws_a.connect()
    await ws_b.connect()
    assert (await ws_a.receive_json_from())["type"] == "me.hello"
    assert (await ws_b.receive_json_from())["type"] == "me.hello"

    await sync_to_async(place)(live_auction, a, "100")
    await sync_to_async(place)(live_auction, b, "110")
    # The private channel carries the bell update and the live outbid notice.
    received = {m["type"]: m for m in [await ws_a.receive_json_from(), await ws_a.receive_json_from()]}
    notice = received["auction.outbid"]
    assert notice["data"]["auction"] == str(live_auction.public_id)
    assert notice["data"]["minimum_next_bid"] == "120.00"
    bell = received["notification.created"]
    assert bell["data"]["kind"] == "auction.outbid" and bell["data"]["link"] == f"/auctions/{live_auction.public_id}"
    assert await ws_b.receive_nothing()
    await ws_a.disconnect()
    await ws_b.disconnect()

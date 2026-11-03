"""WebSockets bound to login sessions (F-AUTH-08)."""

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.db import connections
from django.test import Client

from apps.accounts.models import SessionRevokeReason, UserSession
from apps.accounts.services.sessions import revoke_session
from apps.core.events import reset_event_bus
from apps.realtime.protocol import CLOSE_SESSION_REVOKED, CLOSE_UNAUTHORIZED
from config.asgi import application

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
async def _close_thread_connections():
    """Database work in consumers runs in asgiref's worker thread; close its connection."""
    yield
    await sync_to_async(connections.close_all)()


@pytest.fixture(autouse=True)
def channels_bus(settings):
    settings.EVENT_BUS_BACKEND = "apps.realtime.publisher.ChannelsEventBus"
    reset_event_bus()


def _cookie_for(user) -> bytes:
    client = Client()
    client.force_login(user)
    return f"{settings.SESSION_COOKIE_NAME}={client.cookies[settings.SESSION_COOKIE_NAME].value}".encode()


def socket(path: str, cookie: bytes | None = None) -> WebsocketCommunicator:
    headers = [(b"origin", b"http://localhost")]
    if cookie:
        headers.append((b"cookie", cookie))
    return WebsocketCommunicator(application, path, headers=headers)


async def test_private_channel_requires_login():
    ws = socket("/ws/me/")
    connected, code = await ws.connect()
    assert not connected and code == CLOSE_UNAUTHORIZED


async def test_signed_in_socket_closes_when_session_is_revoked(make_user):
    user = await sync_to_async(make_user)()
    cookie = await sync_to_async(_cookie_for)(user)

    me = socket("/ws/me/", cookie)
    system = socket("/ws/system/", cookie)
    assert (await me.connect())[0]
    assert (await me.receive_json_from())["type"] == "me.hello"
    assert (await system.connect())[0]
    assert (await system.receive_json_from())["data"] == {"authenticated": True}

    tracked = await sync_to_async(UserSession.objects.get)(user=user)
    await sync_to_async(revoke_session)(tracked, SessionRevokeReason.ADMIN)

    for ws in (me, system):
        assert (await ws.receive_json_from())["type"] == "session.revoked"
        assert (await ws.receive_output())["code"] == CLOSE_SESSION_REVOKED


async def test_revoked_session_cannot_reconnect(make_user):
    user = await sync_to_async(make_user)()
    cookie = await sync_to_async(_cookie_for)(user)
    tracked = await sync_to_async(UserSession.objects.get)(user=user)
    await sync_to_async(revoke_session)(tracked, SessionRevokeReason.LOGOUT)
    connected, code = await socket("/ws/me/", cookie).connect()
    assert not connected and code == CLOSE_SESSION_REVOKED

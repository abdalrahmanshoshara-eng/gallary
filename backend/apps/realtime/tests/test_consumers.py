import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.db import connections

from config.asgi import application


@pytest.fixture(autouse=True)
async def _close_thread_connections():
    """Database work in consumers runs in asgiref's worker thread; close its connection."""
    yield
    await sync_to_async(connections.close_all)()


def communicator(origin: bytes = b"http://localhost") -> WebsocketCommunicator:
    return WebsocketCommunicator(application, "/ws/system/", headers=[(b"origin", origin)])


@pytest.mark.django_db(transaction=True)
async def test_system_socket_greets_anonymous_client_with_server_time():
    ws = communicator()
    connected, _ = await ws.connect()
    assert connected
    hello = await ws.receive_json_from()
    assert hello["type"] == "system.hello"
    assert hello["data"] == {"authenticated": False}
    assert hello["server_time"].endswith("Z")
    await ws.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_ping_returns_pong_with_server_time():
    ws = communicator()
    await ws.connect()
    await ws.receive_json_from()
    await ws.send_json_to({"type": "ping", "client_time": 1730000000000})
    pong = await ws.receive_json_from()
    assert pong["type"] == "pong"
    assert pong["data"]["client_time"] == 1730000000000
    assert "server_time" in pong
    await ws.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_invalid_and_unsupported_messages_are_rejected_without_closing():
    ws = communicator()
    await ws.connect()
    await ws.receive_json_from()
    await ws.send_to(text_data="not json")
    assert (await ws.receive_json_from())["data"]["code"] == "INVALID_MESSAGE"
    await ws.send_json_to({"type": "bid.place", "amount": 10})
    assert (await ws.receive_json_from())["data"]["code"] == "UNSUPPORTED_TYPE"
    await ws.send_to(text_data="x" * 5000)
    assert (await ws.receive_json_from())["data"]["code"] == "INVALID_MESSAGE"
    await ws.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_cross_site_origin_is_refused():
    ws = communicator(origin=b"https://evil.example")
    connected, _ = await ws.connect()
    assert not connected

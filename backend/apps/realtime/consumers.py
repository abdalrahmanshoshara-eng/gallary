"""
WebSocket consumers.

Consumers only transport messages: they never accept or reject business operations (bids
are placed over HTTP, ADR-10) and never query the database per broadcast message.
"""

from __future__ import annotations

import logging
from typing import Any

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .protocol import envelope

logger = logging.getLogger(__name__)

MAX_INBOUND_MESSAGE_BYTES = 4096


class BaseJsonConsumer(AsyncJsonWebsocketConsumer):
    """Common behaviour: heartbeat, group relay, strict inbound validation."""

    groups: list[str] = []

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None, **kwargs: Any) -> None:
        if bytes_data is not None or text_data is None or len(text_data) > MAX_INBOUND_MESSAGE_BYTES:
            await self.send_json(envelope("error", {"code": "INVALID_MESSAGE"}))
            return
        await super().receive(text_data=text_data, **kwargs)

    @classmethod
    async def decode_json(cls, text_data: str) -> Any:
        try:
            return await super().decode_json(text_data)
        except ValueError:
            return None

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        if not isinstance(content, dict) or not isinstance(content.get("type"), str):
            await self.send_json(envelope("error", {"code": "INVALID_MESSAGE"}))
            return
        if content["type"] == "ping":
            await self.send_json(envelope("pong", {"client_time": content.get("client_time")}))
            return
        await self.handle_message(content)

    async def handle_message(self, content: dict[str, Any]) -> None:
        """Subclasses handle their own inbound message types (read-only subscriptions)."""
        await self.send_json(envelope("error", {"code": "UNSUPPORTED_TYPE", "type": content["type"]}))

    async def broadcast_message(self, event: dict[str, Any]) -> None:
        """Relay a group message published by `ChannelsEventBus`."""
        await self.send_json(event["payload"])


class SystemConsumer(BaseJsonConsumer):
    """
    `/ws/system/` — connectivity and clock synchronisation.

    Used by the frontend to verify the realtime path end to end and to estimate the
    offset between the browser clock and the server clock (ping/pong carry server_time).
    """

    async def connect(self) -> None:
        await self.accept()
        user = self.scope.get("user")
        await self.send_json(envelope("system.hello", {"authenticated": bool(user and user.is_authenticated)}))

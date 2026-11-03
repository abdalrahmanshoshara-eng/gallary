"""
WebSocket consumers.

Consumers only transport messages: they never accept or reject business operations (bids
are placed over HTTP, ADR-10) and never query the database per broadcast message.

Authenticated sockets are bound to the login session: they join `session.<id>` and are
closed with 4409 as soon as that session is revoked (logout, admin action, deactivation).
"""

from __future__ import annotations

import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.services.sessions import SESSION_ID_KEY, session_is_active

from .mappers.accounts import session_group, user_group
from .protocol import CLOSE_SESSION_REVOKED, CLOSE_UNAUTHORIZED, envelope

logger = logging.getLogger(__name__)

MAX_INBOUND_MESSAGE_BYTES = 4096


class BaseJsonConsumer(AsyncJsonWebsocketConsumer):
    """Common behaviour: session binding, heartbeat, group relay, strict inbound validation."""

    #: Reject anonymous connections with 4401.
    requires_auth = False

    async def connect(self) -> None:
        self.joined: list[str] = []
        user = self.scope.get("user")
        authenticated = bool(user and user.is_authenticated)
        if authenticated:
            session_id = self.scope.get("session", {}).get(SESSION_ID_KEY)
            if not session_id or not await database_sync_to_async(session_is_active)(session_id, user.pk):
                await self.close(code=CLOSE_SESSION_REVOKED)
                return
            await self._join(session_group(session_id))
            await self._join(user_group(user.pk))
        elif self.requires_auth:
            await self.close(code=CLOSE_UNAUTHORIZED)
            return
        await self.accept()
        await self.on_connected(authenticated)

    async def on_connected(self, authenticated: bool) -> None:
        """Hook for subclasses: send the initial snapshot."""

    async def _join(self, group: str) -> None:
        await self.channel_layer.group_add(group, self.channel_name)
        self.joined.append(group)

    async def disconnect(self, code: int) -> None:
        for group in getattr(self, "joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

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
        payload = event["payload"]
        await self.send_json(payload)
        if payload.get("type") == "session.revoked":
            await self.close(code=CLOSE_SESSION_REVOKED)


class SystemConsumer(BaseJsonConsumer):
    """`/ws/system/` — connectivity and clock synchronisation (anonymous allowed)."""

    async def on_connected(self, authenticated: bool) -> None:
        await self.send_json(envelope("system.hello", {"authenticated": authenticated}))


class MeConsumer(BaseJsonConsumer):
    """`/ws/me/` — the signed-in user's private channel (outbid, auction won … from Phase 6)."""

    requires_auth = True

    async def on_connected(self, authenticated: bool) -> None:
        await self.send_json(envelope("me.hello", {}))

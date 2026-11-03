"""Event bus implementation that fans domain events out through the Channels layer."""

from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.core.events import DomainEvent

from .protocol import GROUP_MESSAGE_TYPE
from .registry import messages_for

logger = logging.getLogger(__name__)


class ChannelsEventBus:
    """
    Publishes the realtime messages mapped from a domain event to their groups.

    Called from `publish_on_commit`, i.e. only after the database transaction committed.
    Works from sync code (WSGI API, Celery). Delivery is best-effort; clients recover
    missed messages via `seq` gap detection and a REST resync (ADR-11).
    """

    def publish(self, event: DomainEvent) -> None:
        messages = messages_for(event)
        if not messages:
            return
        layer = get_channel_layer()
        if layer is None:
            logger.error("channel_layer_not_configured")
            return
        send = async_to_sync(layer.group_send)
        for message in messages:
            send(message.group, {"type": GROUP_MESSAGE_TYPE, "payload": message.to_payload()})

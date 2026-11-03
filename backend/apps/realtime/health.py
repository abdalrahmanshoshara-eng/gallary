"""Readiness check for the Channels layer (contributed to core via settings.HEALTH_CHECKS)."""

from __future__ import annotations

import asyncio

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.core.health import CheckResult, timed_check


async def _round_trip() -> None:
    layer = get_channel_layer()
    if layer is None:
        raise RuntimeError("channel layer not configured")
    channel = await layer.new_channel("health.")
    await layer.send(channel, {"type": "health.probe"})
    message = await asyncio.wait_for(layer.receive(channel), timeout=2)
    if message.get("type") != "health.probe":
        raise RuntimeError("unexpected channel layer message")


def check_channel_layer() -> CheckResult:
    return timed_check("channel_layer", async_to_sync(_round_trip))

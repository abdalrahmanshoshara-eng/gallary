"""
WebSocket message protocol (ARCHITECTURE §5.4).

Every server → client message has the same envelope:

    {"type": "bid.placed", "seq": 128, "server_time": "...Z", "data": {...}}

`seq` is present for stream messages that clients must apply in order (auction events);
control messages (hello, pong, error) omit it. `server_time` lets clients estimate clock
offset; clients never make decisions from their own clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

# Close codes (4000–4999 are application-defined).
CLOSE_NORMAL = 1000
CLOSE_SERVICE_RESTART = 1012  # graceful redeploy: clients reconnect with backoff
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
CLOSE_SESSION_REVOKED = 4409

# Consumers relay group messages through this handler name.
GROUP_MESSAGE_TYPE = "broadcast.message"


def server_time_iso() -> str:
    return timezone.now().isoformat().replace("+00:00", "Z")


def envelope(message_type: str, data: dict[str, Any] | None = None, *, seq: int | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"type": message_type, "server_time": server_time_iso(), "data": data or {}}
    if seq is not None:
        message["seq"] = seq
    return message


@dataclass(frozen=True)
class RealtimeMessage:
    """A message to deliver to every connection subscribed to `group`."""

    group: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    seq: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return envelope(self.type, self.data, seq=self.seq)

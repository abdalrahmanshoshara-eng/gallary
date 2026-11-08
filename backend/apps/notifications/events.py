"""Notification domain events (transport lives in apps.realtime)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from apps.core.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class NotificationCreated(DomainEvent):
    """Tells the user's open tabs to refresh the bell (`/ws/me/`)."""

    name: ClassVar[str] = "notification.created"
    user_id: int
    notification_id: str
    kind: str
    title: str
    link: str = ""

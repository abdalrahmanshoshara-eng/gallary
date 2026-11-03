"""
Domain events and the event bus (ADR-05v2, ADR-11).

Domain services publish events after their transaction commits. They depend only on the
`EventBus` protocol defined here; the concrete transport (Channels/WebSockets) lives in
`apps.realtime` and is selected by the `EVENT_BUS_BACKEND` setting. Domain apps must never
import `apps.realtime` or `channels` (enforced by import-linter).

PostgreSQL remains the source of truth: a lost event is recovered by clients through
sequence-gap detection and a state resync, so publishing is best-effort by design.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import ClassVar, Protocol

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for immutable domain events. Subclasses set a unique `name`."""

    name: ClassVar[str] = "domain.event"
    occurred_at: datetime = field(default_factory=timezone.now)


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class InMemoryEventBus:
    """Collects events in memory. Used by tests and as a safe no-transport default."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    bus_class = import_string(settings.EVENT_BUS_BACKEND)
    return bus_class()


def reset_event_bus() -> None:
    """Drop the cached bus instance (tests, settings overrides)."""
    get_event_bus.cache_clear()


def _safe_publish(event: DomainEvent) -> None:
    try:
        get_event_bus().publish(event)
    except Exception:
        logger.exception("event_publish_failed", extra={"event": event.name})


def publish_on_commit(event: DomainEvent) -> None:
    """Publish `event` once the surrounding transaction commits (immediately if none)."""
    transaction.on_commit(lambda: _safe_publish(event))

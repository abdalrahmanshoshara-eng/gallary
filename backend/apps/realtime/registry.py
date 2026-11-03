"""
Maps domain events to realtime messages.

Each realtime-aware feature registers a mapper for its domain events here, inside the
realtime app (e.g. `apps/realtime/mappers/auctions.py` in Phase 6). Domain code stays
unaware of groups, envelopes or WebSockets.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from apps.core.events import DomainEvent

from .protocol import RealtimeMessage

Mapper = Callable[[DomainEvent], Iterable[RealtimeMessage]]

_registry: dict[type[DomainEvent], Mapper] = {}


def register(event_class: type[DomainEvent]) -> Callable[[Mapper], Mapper]:
    def decorator(mapper: Mapper) -> Mapper:
        if event_class in _registry:
            raise ValueError(f"realtime mapper already registered for {event_class.__name__}")
        _registry[event_class] = mapper
        return mapper

    return decorator


def unregister(event_class: type[DomainEvent]) -> None:
    _registry.pop(event_class, None)


def messages_for(event: DomainEvent) -> list[RealtimeMessage]:
    mapper = _registry.get(type(event))
    return list(mapper(event)) if mapper else []

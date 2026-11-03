"""Domain events published by the accounts app."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from apps.core.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class SessionRevoked(DomainEvent):
    name = "accounts.session_revoked"
    session_public_id: UUID
    user_id: int
    reason: str

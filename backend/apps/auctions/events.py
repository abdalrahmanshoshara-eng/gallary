"""Auction domain events (published after commit; transport lives in apps.realtime)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from apps.core.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class AuctionEvent(DomainEvent):
    """A public change of an auction. `seq` = auction.version (BR-507b)."""

    name: ClassVar[str] = "auction.event"
    auction_public_id: str
    seq: int
    type: str  # bid.placed, auction.started, auction.extended, auction.ended, …
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class BidderNotice(DomainEvent):
    """A private notice for one user (outbid, won, lost the award)."""

    name: ClassVar[str] = "auction.notice"
    user_id: int
    type: str  # auction.outbid, auction.won, auction.award_lost
    data: dict[str, Any] = field(default_factory=dict)

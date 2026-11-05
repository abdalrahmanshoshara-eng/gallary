"""Auction events → the auction's public stream and the bidder's private channel."""

from apps.auctions.events import AuctionEvent, BidderNotice

from ..protocol import RealtimeMessage
from ..registry import register
from .accounts import user_group


def auction_group(public_id) -> str:
    return f"auction.{public_id}"


@register(AuctionEvent)
def auction_event(event: AuctionEvent):
    # Ordered stream: clients apply by `seq` and resync over REST on a gap (ARCHITECTURE §5.4).
    yield RealtimeMessage(group=auction_group(event.auction_public_id), type=event.type, data=event.data, seq=event.seq)


@register(BidderNotice)
def bidder_notice(event: BidderNotice):
    # Private: outbid / won / award lost, shown on any page through /ws/me/.
    yield RealtimeMessage(group=user_group(event.user_id), type=event.type, data=event.data)

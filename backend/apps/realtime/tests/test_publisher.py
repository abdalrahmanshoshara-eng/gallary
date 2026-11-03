from dataclasses import dataclass

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.core.events import DomainEvent
from apps.realtime import registry
from apps.realtime.health import check_channel_layer
from apps.realtime.protocol import GROUP_MESSAGE_TYPE, RealtimeMessage
from apps.realtime.publisher import ChannelsEventBus


@dataclass(frozen=True, kw_only=True)
class PriceChanged(DomainEvent):
    name = "test.price_changed"
    item: str
    price: str
    version: int


@pytest.fixture
def mapped_event():
    @registry.register(PriceChanged)
    def _map(event):
        yield RealtimeMessage(
            group=f"item.{event.item}", type="price.changed", data={"price": event.price}, seq=event.version
        )

    yield
    registry.unregister(PriceChanged)


def test_publisher_delivers_mapped_message_to_group(mapped_event):
    layer = get_channel_layer()
    channel = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)("item.a1", channel)

    ChannelsEventBus().publish(PriceChanged(item="a1", price="150.00", version=7))

    message = async_to_sync(layer.receive)(channel)
    assert message["type"] == GROUP_MESSAGE_TYPE
    payload = message["payload"]
    assert payload["type"] == "price.changed"
    assert payload["seq"] == 7
    assert payload["data"] == {"price": "150.00"}
    assert payload["server_time"].endswith("Z")


def test_unmapped_events_are_ignored():
    ChannelsEventBus().publish(PriceChanged(item="b", price="1", version=1))


def test_duplicate_mapper_registration_is_an_error(mapped_event):
    with pytest.raises(ValueError):
        registry.register(PriceChanged)(lambda e: [])


def test_channel_layer_health_round_trip():
    assert check_channel_layer().status == "ok"

from dataclasses import dataclass

import pytest
from django.db import transaction
from django.test import override_settings

from apps.core.events import DomainEvent, get_event_bus, publish_on_commit, reset_event_bus


@dataclass(frozen=True, kw_only=True)
class SomethingHappened(DomainEvent):
    name = "test.something_happened"
    value: int


@pytest.mark.django_db(transaction=True)
def test_event_is_published_only_after_commit():
    bus = get_event_bus()
    with transaction.atomic():
        publish_on_commit(SomethingHappened(value=1))
        assert bus.events == []
    assert [e.value for e in bus.events] == [1]


@pytest.mark.django_db(transaction=True)
def test_event_is_dropped_when_transaction_rolls_back():
    bus = get_event_bus()
    with pytest.raises(RuntimeError), transaction.atomic():
        publish_on_commit(SomethingHappened(value=2))
        raise RuntimeError("rollback")
    assert bus.events == []


class ExplodingBus:
    def publish(self, event):
        raise ConnectionError("transport down")


@pytest.mark.django_db(transaction=True)
@override_settings(EVENT_BUS_BACKEND="apps.core.tests.test_events.ExplodingBus")
def test_transport_failure_never_breaks_the_committed_operation():
    reset_event_bus()
    with transaction.atomic():
        publish_on_commit(SomethingHappened(value=3))
    # Reaching this line means the failure was contained and logged.

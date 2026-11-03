import os

import pytest

from apps.core.events import reset_event_bus


def pytest_collection_modifyitems(config, items):
    if os.environ.get("REDIS_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="set REDIS_INTEGRATION=1 to run tests against a real Redis")
    for item in items:
        if "redis" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _fresh_event_bus():
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()

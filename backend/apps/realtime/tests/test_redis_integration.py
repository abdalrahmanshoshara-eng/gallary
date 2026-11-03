"""Runs only with REDIS_INTEGRATION=1 against the real Redis URLs from the environment."""

import os

import pytest
from channels.layers import channel_layers
from django.test import override_settings

pytestmark = [pytest.mark.redis, pytest.mark.django_db]

REAL_REDIS = {
    "CACHES": {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ.get("REDIS_CACHE_URL", ""),
        }
    },
    "CHANNEL_LAYERS": {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [os.environ.get("CHANNEL_LAYER_URL", "")]},
        }
    },
}


@pytest.fixture
def real_redis():
    with override_settings(**REAL_REDIS):
        channel_layers.backends.clear()
        yield
    channel_layers.backends.clear()


def test_every_readiness_check_passes_against_real_services(api_client, real_redis):
    response = api_client.get("/api/v1/health/ready")
    statuses = {c["name"]: c["status"] for c in response.json()["checks"]}
    for name in ("database", "cache", "broker", "channel_layer"):
        assert statuses[name] == "ok", statuses

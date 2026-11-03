import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.core import health
from apps.core.health import CheckResult
from apps.core.tasks import scheduler_heartbeat

LOCAL_CHECKS = [
    "apps.core.health.check_database",
    "apps.core.health.check_cache",
    "apps.core.health.check_scheduler",
    "apps.realtime.health.check_channel_layer",
]


def failing_check() -> CheckResult:
    return CheckResult("broker", "error", 0.0, "ConnectionError")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def test_liveness_needs_no_dependencies(api_client):
    response = api_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "server_time" in response.json()
    assert response["Cache-Control"].startswith("max-age=0")


@pytest.mark.django_db
@override_settings(HEALTH_CHECKS=LOCAL_CHECKS)
def test_readiness_ok_when_critical_checks_pass(api_client):
    scheduler_heartbeat.delay()
    response = api_client.get("/api/v1/health/ready")
    body = response.json()
    assert response.status_code == 200, body
    assert body["status"] == "ready"
    assert {c["name"]: c["status"] for c in body["checks"]} == {
        "database": "ok",
        "cache": "ok",
        "scheduler": "ok",
        "channel_layer": "ok",
    }


@pytest.mark.django_db
@override_settings(HEALTH_CHECKS=[*LOCAL_CHECKS, "apps.core.tests.test_health.failing_check"])
def test_readiness_503_when_a_critical_check_fails(api_client):
    response = api_client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.django_db
@override_settings(HEALTH_CHECKS=LOCAL_CHECKS)
def test_missing_scheduler_heartbeat_is_degraded_not_failing(api_client):
    response = api_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    statuses = {c["name"]: c["status"] for c in response.json()["checks"]}
    assert statuses["scheduler"] == "degraded"


@override_settings(SCHEDULER_HEARTBEAT_STALE_AFTER=60)
def test_stale_scheduler_heartbeat_is_degraded():
    cache.set(health.SCHEDULER_HEARTBEAT_CACHE_KEY, timezone.now().timestamp() - 600)
    assert health.check_scheduler().status == "degraded"


def test_check_reports_exception_type_without_raising():
    def boom():
        raise ConnectionError("secret details must not leak")

    result = health.timed_check("x", boom)
    assert result.status == "error"
    assert result.detail == "ConnectionError"

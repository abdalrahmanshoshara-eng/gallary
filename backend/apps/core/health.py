"""
Readiness checks.

Each check is a small callable returning `CheckResult`. The list of checks is configured
in `settings.HEALTH_CHECKS` so that apps (e.g. realtime) can contribute checks without the
core app importing them.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

SCHEDULER_HEARTBEAT_CACHE_KEY = "health:scheduler:last_beat"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "ok" | "degraded" | "error"
    latency_ms: float
    detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def timed_check(name: str, func: Callable[[], str | None]) -> CheckResult:
    started = time.perf_counter()
    try:
        detail = func() or ""
        status = "ok"
    except Exception as exc:  # noqa: BLE001 — a failing dependency must be reported, not raised
        logger.warning("health_check_failed", extra={"check": name, "error": type(exc).__name__})
        detail, status = type(exc).__name__, "error"
    return CheckResult(name, status, round((time.perf_counter() - started) * 1000, 2), detail)


def check_database() -> CheckResult:
    def _run() -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    return timed_check("database", _run)


def check_cache() -> CheckResult:
    def _run() -> None:
        key = "health:cache:probe"
        cache.set(key, "1", timeout=10)
        if cache.get(key) != "1":
            raise RuntimeError("cache round-trip mismatch")

    return timed_check("cache", _run)


def check_broker() -> CheckResult:
    def _run() -> None:
        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
        try:
            client.ping()
        finally:
            client.close()

    return timed_check("broker", _run)


def check_scheduler() -> CheckResult:
    """Degraded (not failed) when Celery beat has not run its heartbeat recently."""
    started = time.perf_counter()
    try:
        last_beat = cache.get(SCHEDULER_HEARTBEAT_CACHE_KEY)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("scheduler", "error", 0.0, type(exc).__name__)
    latency = round((time.perf_counter() - started) * 1000, 2)
    if last_beat is None:
        return CheckResult("scheduler", "degraded", latency, "no heartbeat recorded")
    age = timezone.now().timestamp() - float(last_beat)
    if age > settings.SCHEDULER_HEARTBEAT_STALE_AFTER:
        return CheckResult("scheduler", "degraded", latency, f"last heartbeat {int(age)}s ago")
    return CheckResult("scheduler", "ok", latency, f"last heartbeat {int(age)}s ago")


def run_checks() -> tuple[bool, list[CheckResult]]:
    """Run every configured check. Ready unless a critical check reports an error."""
    results = [import_string(path)() for path in settings.HEALTH_CHECKS]
    non_critical = set(settings.HEALTH_NON_CRITICAL)
    ready = all(r.status != "error" for r in results if r.name not in non_critical)
    return ready, results

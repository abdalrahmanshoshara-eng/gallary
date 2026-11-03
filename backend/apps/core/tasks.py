"""Core background tasks."""

from __future__ import annotations

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from .health import SCHEDULER_HEARTBEAT_CACHE_KEY


@shared_task(name="apps.core.tasks.scheduler_heartbeat", ignore_result=True)
def scheduler_heartbeat() -> float:
    """
    Scheduled by Celery beat every minute on the `critical` queue.

    Records the time it ran so `/health/ready` can report whether the scheduler and the
    critical-queue workers are alive (auction and reservation expiry depend on both).
    """
    now = timezone.now().timestamp()
    cache.set(SCHEDULER_HEARTBEAT_CACHE_KEY, now, timeout=None)
    return now

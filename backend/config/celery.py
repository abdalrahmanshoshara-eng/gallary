"""
Celery application.

Queues (ARCHITECTURE §7.5): critical (auctions, reservation expiry), default, media,
notifications. Exactly one beat process runs, using the database scheduler.
The request id of the code that enqueued a task is propagated into the task's logs.
"""

from __future__ import annotations

import os

from celery import Celery, signals
from kombu import Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("damascene")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.task_queues = [Queue(name) for name in ("critical", "default", "media", "notifications")]
app.autodiscover_tasks()

_REQUEST_ID_HEADER = "request_id"
_tokens: dict[str, object] = {}


@signals.before_task_publish.connect
def _attach_request_id(headers: dict | None = None, **_: object) -> None:
    from apps.core.request_context import get_request_id

    if headers is not None and _REQUEST_ID_HEADER not in headers:
        headers[_REQUEST_ID_HEADER] = get_request_id()


@signals.task_prerun.connect
def _bind_request_id(task_id: str | None = None, task=None, **_: object) -> None:
    from apps.core.request_context import new_request_id, set_request_id

    request_id = getattr(task.request, _REQUEST_ID_HEADER, None) if task else None
    if task_id:
        _tokens[task_id] = set_request_id(request_id or new_request_id())


@signals.task_postrun.connect
def _unbind_request_id(task_id: str | None = None, **_: object) -> None:
    from apps.core.request_context import reset_request_id

    token = _tokens.pop(task_id, None) if task_id else None
    if token is not None:
        reset_request_id(token)

"""Recording audit entries. Call inside the same transaction as the audited change."""

from __future__ import annotations

from typing import Any

from django.db import models

from apps.core.request_context import get_request_id

from .models import AuditLog


def record(
    *,
    actor: models.Model | None,
    action: str,
    entity: models.Model | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    changes: dict[str, Any] | None = None,
    reason: str = "",
    ip: str | None = None,
) -> AuditLog:
    if entity is not None:
        entity_type = entity_type or entity._meta.label_lower
        entity_id = entity_id or str(getattr(entity, "public_id", None) or entity.pk)
    if not entity_type or not entity_id:
        raise ValueError("audit.record needs an entity or entity_type + entity_id")
    return AuditLog.objects.create(
        actor=actor if actor is not None and getattr(actor, "pk", None) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
        reason=reason,
        ip=ip,
        request_id=get_request_id() or "",
    )

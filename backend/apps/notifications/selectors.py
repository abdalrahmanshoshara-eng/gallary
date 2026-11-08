from __future__ import annotations

from django.db.models import QuerySet

from .models import Notification


def for_user(user, *, unread: bool = False) -> QuerySet[Notification]:
    qs = Notification.objects.filter(user=user)
    return qs.filter(read_at__isnull=True) if unread else qs


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).count()

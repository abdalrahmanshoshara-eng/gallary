"""Staff roles (PRD §3, §8). Roles are Django Groups; permissions attach to them per phase."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import models


class Role(models.TextChoices):
    CONTENT_STAFF = "content_staff", "موظف المحتوى"
    OPERATIONS_STAFF = "operations_staff", "موظف العمليات"
    AUCTION_MANAGER = "auction_manager", "مدير المزادات"
    SUPER_ADMIN = "super_admin", "المدير العام"


ROLE_NAMES = frozenset(Role.values)


def user_roles(user) -> list[str]:
    if not getattr(user, "is_authenticated", False) or not user.is_staff:
        return []
    names = {g.name for g in user.groups.all() if g.name in ROLE_NAMES}
    if user.is_superuser:
        names.add(Role.SUPER_ADMIN)
    return sorted(names)


def has_any_role(user, roles: Iterable[str]) -> bool:
    wanted = set(roles)
    return bool(wanted.intersection(user_roles(user)))


def is_super_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and user.is_active
        and user.is_staff
        and (user.is_superuser or user.groups.filter(name=Role.SUPER_ADMIN).exists())
    )

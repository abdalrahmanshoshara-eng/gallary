from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from .models import User, UserSession


def active_sessions_for(user: User) -> QuerySet[UserSession]:
    return UserSession.objects.filter(user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()).order_by(
        "-last_seen_at"
    )


def _with_groups(qs: QuerySet[User]) -> QuerySet[User]:
    from django.contrib.auth.models import Group

    return qs.prefetch_related(Prefetch("groups", queryset=Group.objects.only("id", "name")))


def staff_users() -> QuerySet[User]:
    return _with_groups(User.objects.filter(is_staff=True)).order_by("display_name", "phone")


def search_users(*, search: str = "", kind: str = "", is_active: bool | None = None) -> QuerySet[User]:
    qs = User.objects.all()
    if kind == "staff":
        qs = qs.filter(is_staff=True)
    elif kind == "customer":
        qs = qs.filter(is_staff=False)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    term = search.strip()
    if term:
        digits = "".join(ch for ch in term if ch.isdigit())
        condition = Q(display_name__icontains=term) | Q(email__icontains=term)
        if len(digits) >= 3:
            condition |= Q(phone__contains=digits)
        qs = qs.filter(condition)
    return _with_groups(qs).order_by("-date_joined")

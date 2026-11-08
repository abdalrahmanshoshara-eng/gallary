from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Min, Q, QuerySet, Sum
from django.utils import timezone

from .models import Settlement, SettlementStatus

ZERO = Decimal("0.00")


def staff_settlements(*, status: str = "", search: str = "", payee: str = "") -> QuerySet[Settlement]:
    qs = Settlement.objects.select_related("order_item__order", "order_item__artwork", "paid_by")
    if status in SettlementStatus.values:
        qs = qs.filter(status=status)
    if payee:
        qs = qs.filter(payee_key=payee)
    term = search.strip()
    if term:
        qs = qs.filter(
            Q(payee_name__icontains=term)
            | Q(order_item__order__order_number__icontains=term)
            | Q(order_item__title_snapshot__icontains=term)
            | Q(reference__icontains=term)
        )
    return qs.order_by("created_at") if status in ("pending", "on_hold") else qs.order_by("-created_at")


def _total(qs) -> dict:
    agg = qs.aggregate(count=Count("id"), amount=Sum("payee_amount"))
    return {"count": agg["count"], "amount": agg["amount"] or ZERO}


def summary() -> dict:
    month_start = timezone.localdate().replace(day=1)
    return {
        "pending": _total(Settlement.objects.filter(status=SettlementStatus.PENDING)),
        "on_hold": _total(Settlement.objects.filter(status=SettlementStatus.ON_HOLD)),
        "paid_this_month": _total(Settlement.objects.filter(status=SettlementStatus.PAID, paid_at__gte=month_start)),
    }


def pending_by_payee() -> list[dict]:
    """What each payee is owed now: the natural starting point for paying (one transfer each)."""
    rows = (
        Settlement.objects.filter(status=SettlementStatus.PENDING)
        .values("payee_key", "payee_name", "payee_type")
        .annotate(count=Count("id"), amount=Sum("payee_amount"), oldest=Min("created_at"))
        .order_by("oldest")
    )
    return list(rows)

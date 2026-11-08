"""Settlement workflow (BR-704…706). Every financial change is audited with its reason."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.orders.models import Order, OrderItem, OrderItemStatus, OrderStatus, PayeeType

from .models import Settlement, SettlementStatus

OPEN = (SettlementStatus.PENDING, SettlementStatus.ON_HOLD)
CANCELLING_ORDER_STATUSES = (OrderStatus.CANCELLED_BY_PLATFORM, OrderStatus.CANCELLED_BY_CUSTOMER, OrderStatus.EXPIRED)


class SettlementStateError(ConflictError):
    code = "INVALID_SETTLEMENT_STATE"
    message = "لا يمكن تنفيذ هذه العملية على التسوية في حالتها الحالية."


def _invalid(field: str, message: str) -> ConflictError:
    return ConflictError(message, code="VALIDATION_ERROR", http_status=400, details={field: [message]})


def _required(value: str, field: str, message: str) -> str:
    value = (value or "").strip()
    if not value:
        raise _invalid(field, message)
    return value


# --- creation (BR-704/705) ------------------------------------------------------------------------
def _payee(item: OrderItem) -> dict:
    artwork = item.artwork
    if item.payee_type_snapshot == PayeeType.OWNER and artwork.owner_user_id:
        owner = artwork.owner_user
        return {
            "payee_type": PayeeType.OWNER,
            "owner_user": owner,
            "payee_name": owner.display_name or artwork.owner_name or owner.phone,
            "payee_key": f"owner:{owner.pk}",
        }
    if artwork.artist_id:
        return {
            "payee_type": PayeeType.ARTIST,
            "artist": artwork.artist,
            "payee_name": artwork.artist.name,
            "payee_key": f"artist:{artwork.artist_id}",
        }
    name = artwork.creator_display
    return {"payee_type": PayeeType.ARTIST, "payee_name": name, "payee_key": f"name:{name}"[:40]}


def create_for_order(order: Order) -> list[Settlement]:
    """Idempotent: one settlement per active item, from its snapshot (BR-703)."""
    created = []
    items = order.items.filter(status=OrderItemStatus.ACTIVE, settlement__isnull=True).select_related(
        "artwork__artist", "artwork__owner_user"
    )
    for item in items:
        settlement = Settlement.objects.create(
            order_item=item,
            gross_amount=item.line_total,
            commission_rate=item.commission_rate_snapshot,
            platform_commission=item.commission_amount_snapshot,
            payee_amount=item.payee_amount_snapshot,
            **_payee(item),
        )
        audit.record(
            actor=None,
            action="settlement.created",
            entity=settlement,
            changes={
                "order": order.order_number,
                "payee": settlement.payee_name,
                "amount": str(settlement.payee_amount),
            },
        )
        created.append(settlement)
    return created


def on_order_status_changed(order: Order, from_status: str, to_status: str) -> None:
    """Runs inside the order's transaction."""
    if to_status == OrderStatus.CONFIRMED:
        create_for_order(order)
        return
    if to_status not in CANCELLING_ORDER_STATUSES:
        return
    reason = f"أُلغي الطلب {order.order_number}"
    for settlement in Settlement.objects.select_for_update().filter(order_item__order=order, status__in=OPEN):
        _set(settlement, SettlementStatus.CANCELLED, actor=None, reason=reason, action="settlement.cancelled")
    # Paid settlements stay paid (money already left); the staff view flags them for follow-up.


# --- staff actions --------------------------------------------------------------------------------
def available_actions(settlement: Settlement) -> list[str]:
    return {
        SettlementStatus.PENDING: ["pay", "hold", "cancel"],
        SettlementStatus.ON_HOLD: ["release", "cancel"],
    }.get(settlement.status, [])


def _set(settlement: Settlement, status: str, *, actor, reason: str, action: str) -> Settlement:
    before = settlement.status
    settlement.status = status
    settlement.status_reason = reason
    settlement.save(update_fields=["status", "status_reason", "updated_at"])
    audit.record(actor=actor, action=action, entity=settlement, changes={"from": before, "to": status}, reason=reason)
    return settlement


def _lock(settlement: Settlement) -> Settlement:
    return Settlement.objects.select_for_update().get(pk=settlement.pk)


@transaction.atomic
def hold(settlement: Settlement, *, actor, reason: str) -> Settlement:
    reason = _required(reason, "reason", "سبب التعليق مطلوب.")
    settlement = _lock(settlement)
    if settlement.status != SettlementStatus.PENDING:
        raise SettlementStateError()
    return _set(settlement, SettlementStatus.ON_HOLD, actor=actor, reason=reason, action="settlement.on_hold")


@transaction.atomic
def release(settlement: Settlement, *, actor) -> Settlement:
    settlement = _lock(settlement)
    if settlement.status != SettlementStatus.ON_HOLD:
        raise SettlementStateError()
    return _set(settlement, SettlementStatus.PENDING, actor=actor, reason="", action="settlement.released")


@transaction.atomic
def cancel(settlement: Settlement, *, actor, reason: str) -> Settlement:
    reason = _required(reason, "reason", "سبب الإلغاء مطلوب.")
    settlement = _lock(settlement)
    if settlement.status not in OPEN:
        raise SettlementStateError()
    return _set(settlement, SettlementStatus.CANCELLED, actor=actor, reason=reason, action="settlement.cancelled")


@transaction.atomic
def pay(
    settlements: Iterable[Settlement], *, actor, reference: str, paid_at: date, notes: str = ""
) -> list[Settlement]:
    """BR-706: one transfer outside the platform, recorded for one payee's pending items."""
    reference = _required(reference, "reference", "مرجع التحويل مطلوب (رقم الحوالة أو الإيصال).")
    if paid_at > timezone.localdate():
        raise _invalid("paid_at", "تاريخ الدفع لا يكون في المستقبل.")
    ids = sorted({s.pk for s in settlements})
    if not ids:
        raise _invalid("settlements", "اختر تسوية واحدة على الأقل.")
    locked = list(Settlement.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    if len(locked) != len(ids):
        raise _invalid("settlements", "بعض التسويات غير موجودة.")
    if any(s.status != SettlementStatus.PENDING for s in locked):
        raise SettlementStateError("تُدفع التسويات المستحقة فقط. حدّث الصفحة وراجع الاختيار.")
    if len({s.payee_key for s in locked}) > 1:
        raise _invalid("settlements", "التحويل الواحد لمستفيد واحد. اختر تسويات المستفيد نفسه.")
    for s in locked:
        s.status = SettlementStatus.PAID
        s.status_reason = ""
        s.paid_at = paid_at
        s.reference = reference
        s.notes = notes.strip()
        s.paid_by = actor
        s.save()
        audit.record(
            actor=actor,
            action="settlement.paid",
            entity=s,
            changes={"amount": str(s.payee_amount), "reference": reference, "paid_at": paid_at.isoformat()},
        )
    return locked

"""
Order workflow (BUSINESS_RULES §3.1, §4).

    PENDING_DEPOSIT ──► DEPOSIT_CONFIRMED ──► PAYMENT_PENDING ──► CONFIRMED ──► COMPLETED
         │  └► EXPIRED (system)   └──────────────┴──────► CANCELLED_BY_CUSTOMER / _PLATFORM
         └► CANCELLED_BY_CUSTOMER / CANCELLED_BY_PLATFORM

- Checkout is all-or-nothing: listings are locked in id order, everything is validated,
  then stock is reserved and one order is written (BR-325).
- Expiry is enforced twice: a Beat task every minute and a lazy check before any action on
  an order (BR-308), so an expired order can never be paid.
- Money moves only through PaymentRecord. Order totals and statuses are recomputed from
  confirmed records; transitions that follow from money happen automatically.
"""

from __future__ import annotations

import functools
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status as http

from apps.audit import services as audit
from apps.cart.models import Cart
from apps.core.errors import AppError, ConflictError, PermissionDeniedError
from apps.core.models import SiteSetting
from apps.listings import services as listing_services
from apps.listings.models import Listing

from . import policy
from .models import (
    FINAL_STATUSES,
    Delivery,
    DeliveryStatus,
    DepositStatus,
    Order,
    OrderDepositType,
    OrderItem,
    OrderItemStatus,
    OrderNumberSequence,
    OrderSource,
    OrderStatus,
    OrderStatusHistory,
    PayeeType,
    PaymentKind,
    PaymentRecord,
    PaymentRecordStatus,
    PaymentStatus,
)
from .signals import order_status_changed

ZERO = Decimal("0.00")


# --- errors ------------------------------------------------------------------------------------
class CheckoutError(ConflictError):
    code = "CHECKOUT_FAILED"
    message = "تعذّر إتمام الطلب. راجع العناصر المعلّمة في العربة."


class PriceChangedError(ConflictError):
    code = "PRICE_CHANGED"
    message = "تغيّرت أسعار بعض العناصر منذ إضافتها. راجع الأسعار الجديدة ثم أكّد مجدداً."


class EmptyCartError(ConflictError):
    code = "CART_EMPTY"
    message = "العربة فارغة."


class PolicyNotAcceptedError(AppError):
    code = "POLICY_NOT_ACCEPTED"
    message = "يجب الموافقة على سياسة العربون والإلغاء الحالية."
    http_status = http.HTTP_400_BAD_REQUEST


class PendingLimitError(ConflictError):
    code = "PENDING_ORDERS_LIMIT"
    message = "لديك حجوزات بانتظار العربون بالحد الأقصى المسموح. أكمل أحدها أو ألغِه أولاً."


class DuplicateReservationError(ConflictError):
    code = "ALREADY_RESERVED"
    message = "لديك حجز قائم لهذا العمل بانتظار العربون."


class OrderStateError(ConflictError):
    code = "INVALID_ORDER_STATE"
    message = "لا يمكن تنفيذ هذه العملية في حالة الطلب الحالية."


class OrderExpiredError(ConflictError):
    code = "ORDER_EXPIRED"
    message = "انتهت مهلة هذا الطلب ولم يعد بالإمكان تأكيد العربون (BR-309)."


# --- helpers --------------------------------------------------------------------------------------
def _next_number(now) -> str:
    seq, _ = OrderNumberSequence.objects.select_for_update().get_or_create(year=now.year)
    seq.last_value += 1
    seq.save(update_fields=["last_value"])
    return f"ART-{now.year}-{seq.last_value:06d}"


def _transition(order: Order, to: str, *, actor, reason: str = "") -> None:
    before = order.status
    order.status = to
    if to in FINAL_STATUSES:
        order.closed_at = timezone.now()
    OrderStatusHistory.objects.create(order=order, from_status=before, to_status=to, actor=actor, reason=reason)
    audit.record(actor=actor, action=f"order.{to}", entity=order, changes={"from": before, "to": to}, reason=reason)
    order_status_changed.send(sender=Order, order=order, from_status=before, to_status=to, actor=actor)


def _lock(order: Order) -> Order:
    return Order.objects.select_for_update().get(pk=order.pk)


def _active_items(order: Order):
    return order.items.filter(status=OrderItemStatus.ACTIVE).order_by("listing_id")


def _release_stock(order: Order) -> None:
    for item in _active_items(order):
        listing_services.release(item.listing_id, item.quantity)


# --- checkout (BR-301…313, 325…327) ---------------------------------------------------------------
def checkout(
    *,
    user,
    policy_version: str,
    contact: dict,
    customer_notes: str = "",
) -> Order:
    current_policy = policy.current_version()
    if policy_version != current_policy:
        raise PolicyNotAcceptedError(details={"current_version": current_policy})
    if not user.is_active:
        raise PermissionDeniedError()

    settings_row = SiteSetting.load()
    with transaction.atomic():
        cart = Cart.objects.select_for_update().filter(user=user).first()
        lines = list(cart.items.select_related("listing").order_by("listing_id")) if cart else []
        if not lines:
            raise EmptyCartError()

        # Lock every offer in a stable order (deadlock-free), then validate everything.
        listing_ids = [line.listing_id for line in lines]
        locked = {
            listing.pk: listing
            for listing in Listing.objects.select_for_update(of=("self",))
            .select_related("artwork", "artwork__artist")
            .filter(pk__in=listing_ids)
            .order_by("pk")
        }
        now = timezone.now()
        problems: dict[str, str] = {}
        price_changes: dict[str, dict] = {}
        for line in lines:
            listing = locked[line.listing_id]
            problem = listing_services.purchase_problem(listing, line.quantity, now)
            if problem:
                problems[str(line.public_id)] = problem
            elif listing.price_usd != line.price_at_add:
                price_changes[str(line.public_id)] = {"from": str(line.price_at_add), "to": str(listing.price_usd)}
        if problems:
            raise CheckoutError(details={"items": problems})
        if price_changes:
            raise PriceChangedError(details={"items": price_changes})

        open_orders = Order.objects.filter(user=user, status=OrderStatus.PENDING_DEPOSIT)
        if open_orders.count() >= settings_row.max_pending_orders_per_user:  # BR-311
            raise PendingLimitError(details={"limit": settings_row.max_pending_orders_per_user})
        duplicate = OrderItem.objects.filter(
            order__in=open_orders, listing_id__in=listing_ids, status=OrderItemStatus.ACTIVE
        ).values_list("order__order_number", flat=True)
        if duplicate:  # BR-310
            raise DuplicateReservationError(details={"orders": sorted(set(duplicate))})

        order = Order.objects.create(
            order_number=_next_number(now),
            user=user,
            subtotal=Decimal("0.01"),  # placeholders satisfy the CHECKs until totals are written
            deposit_due=Decimal("0.01"),
            created_at=now,
            reservation_expires_at=now + timedelta(hours=policy.RESERVATION_HOURS),
            policy_version=current_policy,
            policy_accepted_at=now,
            customer_notes=customer_notes.strip(),
            **contact,
        )
        subtotal = deposit = ZERO
        for line in lines:
            listing = listing_services.reserve(line.listing_id, line.quantity)
            line_total = listing.price_usd * line.quantity
            rate = listing_services.commission_rate(listing, settings_row)
            commission, payee = listing_services.split_commission(line_total, rate)
            item_deposit = listing_services.deposit_terms(listing, settings_row).amount_for(line_total, line.quantity)
            OrderItem.objects.create(
                order=order,
                listing=listing,
                artwork=listing.artwork,
                quantity=line.quantity,
                title_snapshot=listing.artwork.title,
                unit_price_snapshot=listing.price_usd,
                line_total=line_total,
                commission_rate_snapshot=rate,
                commission_amount_snapshot=commission,
                payee_amount_snapshot=payee,
                deposit_amount_snapshot=item_deposit,
            )
            subtotal += line_total
            deposit += item_deposit
        order.subtotal = subtotal
        order.deposit_due = min(max(deposit, Decimal("0.01")), subtotal)
        order.save(update_fields=["subtotal", "deposit_due"])
        Delivery.objects.create(order=order)
        OrderStatusHistory.objects.create(order=order, from_status="", to_status=order.status, actor=user)
        audit.record(
            actor=user,
            action="order.created",
            entity=order,
            changes={"number": order.order_number, "subtotal": str(subtotal), "deposit_due": str(order.deposit_due)},
        )
        cart.items.all().delete()  # BR-327: converted lines leave the cart
    return order


# --- expiry (BR-307/308) -----------------------------------------------------------------------------
def expire_if_due(order: Order, now=None) -> bool:
    """Lazy check; call inside a transaction holding the order lock."""
    now = now or timezone.now()
    if order.status == OrderStatus.PENDING_DEPOSIT and order.reservation_expires_at <= now:
        _release_stock(order)
        reason = "انتهت مهلة عربون الفائز." if order.source == OrderSource.AUCTION else "انتهت مهلة العربون (24 ساعة)."
        _transition(order, OrderStatus.EXPIRED, actor=None, reason=reason)
        order.save()
        return True
    return False


def expire_due_orders(now=None) -> int:
    now = now or timezone.now()
    expired = 0
    due = Order.objects.filter(status=OrderStatus.PENDING_DEPOSIT, reservation_expires_at__lte=now)
    for pk in due.values_list("pk", flat=True):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)
            expired += expire_if_due(order, now)
    return expired


def refresh(order: Order) -> Order:
    """Apply a due expiry before showing an order (customers and staff see the truth)."""
    if order.status == OrderStatus.PENDING_DEPOSIT and order.reservation_expires_at <= timezone.now():
        with transaction.atomic():
            locked = _lock(order)
            expire_if_due(locked)
        order.refresh_from_db()
    return order


def _expiring(fn):
    """Commit a due expiry in its own transaction first, then run the action atomically.
    (Expiring inside the action's transaction would be rolled back when the action refuses.)"""

    @functools.wraps(fn)
    def wrapper(target, *args, **kwargs):
        refresh(target.order if isinstance(target, PaymentRecord | OrderItem) else target)
        with transaction.atomic():
            return fn(target, *args, **kwargs)

    return wrapper


def _expired(order: Order) -> bool:
    return order.status == OrderStatus.EXPIRED


# --- customer cancellation (Q9) ---------------------------------------------------------------------
@_expiring
def cancel_by_customer(order: Order, *, user, reason: str = "") -> Order:
    order = _lock(order)
    if order.user_id != user.pk:
        raise PermissionDeniedError()
    if _expired(order):
        raise OrderExpiredError("انتهت مهلة هذا الطلب بالفعل.")
    if order.source == OrderSource.AUCTION:  # BR-507: a winning bid is binding
        raise OrderStateError("طلب المزاد ناتج عن مزايدة ملزمة ولا يُلغى من الحساب. تواصل معنا لأي استفسار.")
    if order.status != OrderStatus.PENDING_DEPOSIT or _confirmed_sum(order) > 0:
        raise OrderStateError("يمكن إلغاء الطلب من حسابك قبل دفع العربون فقط. تواصل معنا لأي تغيير.")
    _release_stock(order)
    order.cancelled_reason = reason.strip()
    _transition(order, OrderStatus.CANCELLED_BY_CUSTOMER, actor=user, reason=reason)
    order.save()
    return order


# --- payments (BR-401…408) ---------------------------------------------------------------------------
def _confirmed_sum(order: Order, kinds=(PaymentKind.DEPOSIT, PaymentKind.PAYMENT)) -> Decimal:
    total = order.payments.filter(status=PaymentRecordStatus.CONFIRMED, kind__in=kinds).aggregate(s=Sum("amount"))["s"]
    return total or ZERO


def _recompute(order: Order, *, actor) -> None:
    """Derive money fields and advance the status when money says so."""
    received = _confirmed_sum(order)
    refunded = _confirmed_sum(order, kinds=(PaymentKind.REFUND,))
    order.amount_paid = received - refunded

    if order.status == OrderStatus.PENDING_DEPOSIT and received >= order.deposit_due:
        order.deposit_status = DepositStatus.CONFIRMED
        _transition(order, OrderStatus.DEPOSIT_CONFIRMED, actor=actor, reason="تأكيد العربون")
    if order.status in (OrderStatus.DEPOSIT_CONFIRMED, OrderStatus.PAYMENT_PENDING):
        if order.amount_paid >= order.subtotal:
            for item in _active_items(order):
                listing_services.confirm_sale(item.listing_id, item.quantity)
            order.confirmed_at = timezone.now()
            _transition(order, OrderStatus.CONFIRMED, actor=actor, reason="اكتمال الدفع")
        elif order.status == OrderStatus.DEPOSIT_CONFIRMED and received > order.deposit_due:
            _transition(order, OrderStatus.PAYMENT_PENDING, actor=actor, reason="استلام دفعة جزئية")

    if refunded and order.deposit_status == DepositStatus.REFUND_DUE and refunded >= min(received, order.deposit_due):
        order.deposit_status = DepositStatus.REFUNDED
    if refunded and refunded >= received:
        order.payment_status = PaymentStatus.REFUNDED
    elif order.amount_paid >= order.subtotal:
        order.payment_status = PaymentStatus.PAID
    elif order.amount_paid > 0:
        order.payment_status = PaymentStatus.PARTIALLY_PAID
    else:
        order.payment_status = PaymentStatus.UNPAID
    order.save()


@_expiring
def record_payment(
    order: Order,
    *,
    actor,
    kind: str,
    amount: Decimal,
    method: str,
    reference: str = "",
    notes: str = "",
    confirm: bool = True,
) -> PaymentRecord:
    order = _lock(order)
    if _expired(order):
        raise OrderExpiredError()
    if kind == PaymentKind.REFUND:
        if _confirmed_sum(order) - _confirmed_sum(order, kinds=(PaymentKind.REFUND,)) < amount:
            raise ConflictError("مبلغ الاسترداد يتجاوز المبالغ المستلمة.", code="REFUND_EXCEEDS_PAID")
    else:
        if order.is_final:
            raise OrderStateError("لا تُسجَّل دفعات على طلب منتهٍ أو ملغى.")
        if order.amount_paid + amount > order.subtotal:
            raise ConflictError(
                "المبلغ يتجاوز المتبقي على الطلب.",
                code="PAYMENT_EXCEEDS_TOTAL",
                details={"remaining": str(order.subtotal - order.amount_paid)},
            )
    record = PaymentRecord.objects.create(
        order=order,
        kind=kind,
        amount=amount,
        method=method,
        reference=reference.strip(),
        notes=notes.strip(),
        recorded_by=actor,
    )
    audit.record(actor=actor, action="payment.recorded", entity=order, changes={"kind": kind, "amount": str(amount)})
    if confirm:
        _confirm(order, record, actor=actor)
    return record


def _confirm(order: Order, record: PaymentRecord, *, actor) -> None:
    record.status = PaymentRecordStatus.CONFIRMED
    record.confirmed_by = actor
    record.confirmed_at = timezone.now()
    record.save(update_fields=["status", "confirmed_by", "confirmed_at"])
    audit.record(
        actor=actor,
        action="payment.confirmed",
        entity=order,
        changes={"kind": record.kind, "amount": str(record.amount)},
    )
    _recompute(order, actor=actor)


@_expiring
def confirm_payment(record: PaymentRecord, *, actor) -> PaymentRecord:
    order = _lock(record.order)
    record = PaymentRecord.objects.select_for_update().get(pk=record.pk)
    if record.status != PaymentRecordStatus.RECORDED:
        raise OrderStateError("هذا السجل ليس بانتظار التأكيد.")
    if _expired(order):
        raise OrderExpiredError()
    if record.kind != PaymentKind.REFUND and (order.is_final or order.amount_paid + record.amount > order.subtotal):
        raise OrderStateError("لا يمكن تأكيد هذه الدفعة في حالة الطلب الحالية.")
    _confirm(order, record, actor=actor)
    return record


@transaction.atomic
def void_payment(record: PaymentRecord, *, actor, reason: str) -> PaymentRecord:
    record = PaymentRecord.objects.select_for_update().get(pk=record.pk)
    if record.status != PaymentRecordStatus.RECORDED:
        raise OrderStateError("السجلات المؤكدة لا تُلغى؛ صحّحها بسجل استرداد (BR-407).")
    if not reason.strip():
        raise ConflictError("سبب الإلغاء مطلوب.", code="REASON_REQUIRED", http_status=400)
    record.status = PaymentRecordStatus.VOIDED
    record.void_reason = reason.strip()
    record.save(update_fields=["status", "void_reason"])
    audit.record(actor=actor, action="payment.voided", entity=record.order, reason=reason)
    return record


# --- staff actions ------------------------------------------------------------------------------------
def _require_reason(reason: str) -> str:
    if not reason.strip():
        raise ConflictError(
            "السبب مطلوب.", code="REASON_REQUIRED", http_status=400, details={"reason": ["السبب مطلوب."]}
        )
    return reason.strip()


@_expiring
def cancel_by_platform(order: Order, *, actor, reason: str) -> Order:
    reason = _require_reason(reason)
    order = _lock(order)
    if _expired(order) or order.is_final:
        raise OrderStateError()
    if order.status == OrderStatus.CONFIRMED:
        for item in _active_items(order):
            listing_services.revert_sale(item.listing_id, item.quantity)
    else:
        _release_stock(order)
    if order.deposit_status == DepositStatus.CONFIRMED or order.amount_paid > 0:
        # BR-405/517: any money received is refunded manually and recorded as REFUND.
        order.deposit_status = DepositStatus.REFUND_DUE
    order.cancelled_reason = reason
    _transition(order, OrderStatus.CANCELLED_BY_PLATFORM, actor=actor, reason=reason)
    order.save()
    return order


@transaction.atomic
def cancel_for_customer(order: Order, *, actor, reason: str) -> Order:
    """Customer withdraws after paying the deposit — staff only; the deposit is forfeited (BR-404)."""
    reason = _require_reason(reason)
    order = _lock(order)
    if order.status not in (OrderStatus.DEPOSIT_CONFIRMED, OrderStatus.PAYMENT_PENDING):
        raise OrderStateError("قبل العربون يلغي العميل من حسابه أو تلغي المنصة الطلب.")
    _release_stock(order)
    order.deposit_status = DepositStatus.FORFEITED
    order.cancelled_reason = reason
    _transition(order, OrderStatus.CANCELLED_BY_CUSTOMER, actor=actor, reason=reason)
    order.save()
    return order


@_expiring
def remove_item(order: Order, item: OrderItem, *, actor, reason: str) -> Order:
    """BR-303/409: before the deposit, drop one item, free its stock and recompute totals."""
    reason = _require_reason(reason)
    order = _lock(order)
    if _expired(order) or order.status != OrderStatus.PENDING_DEPOSIT:
        raise OrderStateError("إزالة العناصر متاحة قبل تأكيد العربون فقط.")
    item = OrderItem.objects.select_for_update().get(pk=item.pk, order=order)
    if item.status != OrderItemStatus.ACTIVE:
        raise OrderStateError("العنصر مُزال بالفعل.")
    if _active_items(order).count() == 1:
        raise OrderStateError("هذا آخر عنصر في الطلب؛ ألغِ الطلب بدلاً من ذلك.")
    listing_services.release(item.listing_id, item.quantity)
    item.status = OrderItemStatus.REMOVED
    item.removed_reason = reason
    item.save(update_fields=["status", "removed_reason"])
    active = list(_active_items(order))
    order.subtotal = sum((i.line_total for i in active), ZERO)
    if order.deposit_type == OrderDepositType.CUSTOM:
        order.deposit_due = min(order.deposit_due, order.subtotal)
    else:
        order.deposit_due = min(sum((i.deposit_amount_snapshot for i in active), ZERO), order.subtotal)
    order.save()
    audit.record(
        actor=actor, action="order.item_removed", entity=order, changes={"item": item.title_snapshot}, reason=reason
    )
    return order


@_expiring
def set_custom_deposit(order: Order, *, actor, amount: Decimal, reason: str) -> Order:
    """Super Admin only (BR-402), before the deposit is confirmed."""
    reason = _require_reason(reason)
    order = _lock(order)
    if _expired(order) or order.status != OrderStatus.PENDING_DEPOSIT:
        raise OrderStateError("يُعدَّل العربون قبل تأكيده فقط.")
    if order.source == OrderSource.AUCTION and amount < (order.subtotal / 2).quantize(Decimal("0.01")):
        raise ConflictError(
            "عربون الفائز في المزاد لا يقل عن 50% من السعر (BR-410).",
            code="VALIDATION_ERROR",
            http_status=400,
            details={"amount": ["عربون الفائز في المزاد لا يقل عن 50% من السعر."]},
        )
    if not (ZERO < amount <= order.subtotal):
        raise ConflictError(
            "العربون يجب أن يكون أكبر من صفر ولا يتجاوز المجموع.",
            code="VALIDATION_ERROR",
            http_status=400,
            details={"amount": ["العربون يجب أن يكون أكبر من صفر ولا يتجاوز المجموع."]},
        )
    before = order.deposit_due
    order.deposit_type = OrderDepositType.CUSTOM
    order.deposit_value = amount
    order.deposit_due = amount
    order.save()
    audit.record(
        actor=actor,
        action="order.deposit_customised",
        entity=order,
        changes={"from": str(before), "to": str(amount)},
        reason=reason,
    )
    _recompute(order, actor=actor)  # an already-paid amount may now cover the new deposit
    return order


@transaction.atomic
def update_delivery(order: Order, *, actor, data: dict) -> Delivery:
    order = _lock(order)
    if order.status not in (OrderStatus.DEPOSIT_CONFIRMED, OrderStatus.PAYMENT_PENDING, OrderStatus.CONFIRMED):
        raise OrderStateError("يُدار التسليم بعد تأكيد العربون وقبل إغلاق الطلب.")
    delivery = order.delivery
    for field in ("method", "carrier_name", "status", "notes"):
        if field in data:
            setattr(delivery, field, data[field])
    if delivery.status == DeliveryStatus.DELIVERED:
        delivery.delivered_at = data.get("delivered_at") or delivery.delivered_at or timezone.now()
    else:
        delivery.delivered_at = None
    delivery.save()
    audit.record(actor=actor, action="order.delivery_updated", entity=order, changes={"status": delivery.status})
    return delivery


@transaction.atomic
def complete(order: Order, *, actor) -> Order:
    order = _lock(order)
    if order.status != OrderStatus.CONFIRMED:
        raise OrderStateError("يُكمَل الطلب بعد تأكيده (اكتمال الدفع).")
    if order.delivery.status != DeliveryStatus.DELIVERED:
        raise OrderStateError("سجّل التسليم أولاً.")
    _transition(order, OrderStatus.COMPLETED, actor=actor)
    order.save()
    return order


def update_internal_notes(order: Order, *, actor, notes: str) -> Order:
    order.internal_notes = notes
    order.save(update_fields=["internal_notes", "updated_at"])
    return order


# --- auction orders (BR-512/513) -----------------------------------------------------------------------
def create_auction_order(*, user, listing_id: int, amount: Decimal, deposit_percent: Decimal, deadline) -> Order:
    """One-item order for an auction winner: stock reserved, deposit ≥ 50% due within the hour.
    Called inside the auction's transaction."""
    listing = listing_services.reserve_for_auction(listing_id)
    rate = listing_services.commission_rate(listing)
    commission, payee = listing_services.split_commission(amount, rate)
    deposit = min((amount * deposit_percent / Decimal(100)).quantize(Decimal("0.01")), amount)
    now = timezone.now()
    order = Order.objects.create(
        order_number=_next_number(now),
        user=user,
        source=OrderSource.AUCTION,
        subtotal=amount,
        deposit_type=OrderDepositType.PERCENTAGE,
        deposit_value=deposit_percent,
        deposit_due=deposit,
        created_at=now,
        reservation_expires_at=deadline,
        payment_deadline=deadline,
        policy_version=policy.current_version(),
        policy_accepted_at=now,
        contact_name=user.display_name or user.phone,
        contact_phone=user.phone,
        contact_email=user.email or "",
        governorate=user.governorate,
        city=user.city,
        address_line=user.address_line,
    )
    OrderItem.objects.create(
        order=order,
        listing=listing,
        artwork=listing.artwork,
        quantity=1,
        title_snapshot=listing.artwork.title,
        unit_price_snapshot=amount,
        line_total=amount,
        commission_rate_snapshot=rate,
        commission_amount_snapshot=commission,
        payee_amount_snapshot=payee,
        payee_type_snapshot=PayeeType.OWNER if listing.artwork.owner_user_id else PayeeType.ARTIST,
        deposit_amount_snapshot=deposit,
    )
    Delivery.objects.create(order=order)
    OrderStatusHistory.objects.create(
        order=order, from_status="", to_status=order.status, actor=None, reason="فوز بمزاد"
    )
    audit.record(actor=None, action="order.created", entity=order, changes={"source": "auction", "amount": str(amount)})
    return order

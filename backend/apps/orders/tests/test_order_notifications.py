"""§26: what the customer is told about their order, and when they are not."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone
from freezegun import freeze_time

from apps.cart import services as cart_services
from apps.notifications.models import Notification
from apps.orders import policy, services
from apps.orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer(make_user):
    return make_user(display_name="ريم", email="reem@example.com")


@pytest.fixture
def ops(make_user):
    return make_user(roles=["operations_staff"])


@pytest.fixture
def place(artwork_factory, listing_factory, buyer):
    def _place(price="1000.00"):
        listing = listing_factory(artwork_factory(published=True), price=price)
        cart_services.add_item(buyer, listing=listing, quantity=1)
        return services.checkout(
            user=buyer,
            policy_version=policy.current_version(),
            contact={"contact_name": "x", "contact_phone": buyer.phone},
        )

    return _place


def kinds(user):
    return list(Notification.objects.filter(user=user).order_by("created_at", "id").values_list("kind", flat=True))


def pay(order, ops, amount, kind="payment"):
    services.record_payment(order, actor=ops, kind=kind, amount=Decimal(amount), method="cash", confirm=True)
    order.refresh_from_db()


def test_order_created_tells_the_deposit_and_deadline(place, buyer, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        order = place()
    n = Notification.objects.get(user=buyer)
    assert n.kind == "order.created" and n.link == f"/orders/{order.order_number}"
    assert order.order_number in n.title and "300 US$" in n.body  # 30% default deposit
    assert len(mail.outbox) == 1


def test_deposit_then_balance(place, buyer, ops):
    order = place()
    pay(order, ops, "300.00", kind="deposit")
    pay(order, ops, "700.00")
    assert kinds(buyer) == ["order.created", "order.deposit_confirmed", "order.confirmed"]
    deposit = Notification.objects.get(kind="order.deposit_confirmed")
    assert "700 US$" in deposit.body  # what is left to pay


def test_paying_everything_at_once_sends_one_notice(place, buyer, ops):
    order = place()
    pay(order, ops, "1000.00")
    assert kinds(buyer) == ["order.created", "order.confirmed"]


def test_deposit_plus_part_payment_sends_one_notice(place, buyer, ops):
    order = place()
    pay(order, ops, "500.00")
    assert kinds(buyer) == ["order.created", "order.deposit_confirmed"]


def test_customer_own_cancel_is_silent_platform_cancel_explains(place, buyer, ops):
    mine = place()
    services.cancel_by_customer(mine, user=buyer)
    assert kinds(buyer) == ["order.created"]

    theirs = place()
    pay(theirs, ops, "300.00", kind="deposit")
    services.cancel_by_platform(theirs, actor=ops, reason="تضرر العمل أثناء النقل")
    n = Notification.objects.get(kind="order.cancelled_by_platform")
    assert "تضرر العمل أثناء النقل" in n.body and "سنعيد إليك ما دفعته" in n.body


def test_expiry_is_announced(place, buyer):
    with freeze_time("2026-11-05 10:00:00"):
        place()
    with freeze_time("2026-11-06 11:00:00"):
        services.expire_due_orders()
    assert kinds(buyer)[-1] == "order.expired"


def test_deposit_reminder_once_in_the_last_three_hours(place, buyer):
    with freeze_time("2026-11-05 10:00:00"):
        order = place()
    with freeze_time("2026-11-06 06:00:00"):  # 4 h left
        assert services.remind_due_deposits() == 0
    with freeze_time("2026-11-06 08:00:00"):  # 2 h left
        assert services.remind_due_deposits() == 1
        assert services.remind_due_deposits() == 0
    n = Notification.objects.get(kind="order.deposit_reminder")
    assert order.order_number in n.title and "300 US$" in n.body


def test_no_reminder_for_paid_or_closed_orders(place, buyer, ops):
    order = place()
    pay(order, ops, "300.00", kind="deposit")
    Order.objects.filter(pk=order.pk).update(
        reservation_expires_at=timezone.now() + timedelta(hours=1), created_at=timezone.now() - timedelta(hours=23)
    )
    assert services.remind_due_deposits() == 0

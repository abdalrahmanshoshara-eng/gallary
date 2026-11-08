import threading
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone
from freezegun import freeze_time

from apps.audit.models import AuditLog
from apps.cart import services as cart_services
from apps.core.models import SiteSetting
from apps.listings import services as listing_services
from apps.orders import policy, services
from apps.orders.models import Order, OrderStatus

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/orders"
CHECKOUT = {
    "accept_policy": True,
    "governorate": "damascus",
    "city": "المالكي",
    "address_line": "شارع أبو رمانة",
    "customer_notes": "الاتصال مساءً",
}


@pytest.fixture
def offer(artwork_factory, listing_factory):
    def _make(**kw):
        return listing_factory(artwork_factory(published=True), **kw)

    return _make


@pytest.fixture
def ops(make_user):
    return make_user(roles=["operations_staff"], display_name="عمليات")


def checkout(client, key=None, **overrides):
    return client.post(
        "/api/v1/orders/checkout",
        {**CHECKOUT, "policy_version": policy.current_version(), **overrides},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex,
    )


def fill_cart(user, *listings_with_qty):
    for listing, qty in listings_with_qty:
        cart_services.add_item(user, listing=listing, quantity=qty)


def order_with(customer, offer, price="1000.00", **kw):
    listing = offer(price=price, **kw)
    fill_cart(customer, (listing, 1))
    order = services.checkout(
        user=customer,
        policy_version=policy.current_version(),
        contact={"contact_name": "x", "contact_phone": customer.phone},
    )
    return order, listing


def pay(order, actor, kind, amount, confirm=True):
    return services.record_payment(
        order, actor=actor, kind=kind, amount=Decimal(amount), method="cash", confirm=confirm
    )


# --- checkout (BR-301…313, 325…327) -------------------------------------------------------------------
def test_checkout_creates_one_order_reserves_stock_and_empties_cart(login_client, customer, offer):
    unique = offer(price="500.00")
    limited = offer(price="40.00", quantity_mode="limited", quantity_total=10, max_per_order=5)
    fill_cart(customer, (unique, 1), (limited, 3))
    response = checkout(login_client(customer))
    assert response.status_code == 201, response.json()
    body = response.json()
    year = timezone.now().year
    assert body["number"] == f"ART-{year}-000001" and body["status"] == "pending_deposit"
    assert body["subtotal"] == "620.00" and body["deposit_due"] == "186.00"  # 30% default per line
    assert body["can_cancel"] is True and len(body["items"]) == 2
    assert body["city"] == "المالكي" and body["contact_phone"] == customer.phone
    unique.refresh_from_db()
    limited.refresh_from_db()
    assert (unique.quantity_available, unique.quantity_reserved) == (0, 1)
    assert (limited.quantity_available, limited.quantity_reserved) == (7, 3)
    assert cart_services.count(customer) == 0
    order = Order.objects.get()
    item = order.items.get(listing=unique)
    assert (item.commission_rate_snapshot, item.commission_amount_snapshot, item.payee_amount_snapshot) == (
        Decimal("15.00"),
        Decimal("75.00"),
        Decimal("425.00"),
    )
    assert order.reservation_expires_at - order.created_at == timedelta(hours=24)
    assert order.policy_version == policy.current_version() and order.history.count() == 1


def test_checkout_is_idempotent(login_client, customer, offer):
    fill_cart(customer, (offer(), 1))
    client = login_client(customer)
    first = checkout(client, key="retry-key-0001")
    again = checkout(client, key="retry-key-0001")
    assert first.status_code == again.status_code == 201
    assert first.json()["number"] == again.json()["number"] and Order.objects.count() == 1
    assert checkout(client).json()["error"]["code"] == "CART_EMPTY"  # a new attempt finds the cart converted
    missing = client.post(
        "/api/v1/orders/checkout", {**CHECKOUT, "policy_version": policy.current_version()}, format="json"
    )
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_policy_must_be_accepted_in_its_current_version(login_client, customer, offer):
    fill_cart(customer, (offer(), 1))
    client = login_client(customer)
    assert "accept_policy" in checkout(client, accept_policy=False).json()["error"]["details"]
    assert checkout(client, policy_version="2020-01-01").json()["error"]["code"] == "POLICY_NOT_ACCEPTED"
    assert not Order.objects.exists()


def test_price_change_refuses_checkout_without_side_effects(login_client, customer, offer):
    listing = offer(price="100.00")
    fill_cart(customer, (listing, 1))
    listing_services.set_pricing(
        listing,
        actor=None,
        price_usd=Decimal("150.00"),
        commission_rate_override=None,
        deposit_type="",
        deposit_value=None,
    )
    response = checkout(login_client(customer))
    assert response.status_code == 409 and response.json()["error"]["code"] == "PRICE_CHANGED"
    listing.refresh_from_db()
    assert listing.quantity_reserved == 0 and not Order.objects.exists() and cart_services.count(customer) == 1


def test_checkout_is_all_or_nothing(login_client, customer, offer):
    from apps.artworks import services as artwork_services

    ok = offer()
    gone = offer()
    fill_cart(customer, (ok, 1), (gone, 1))
    artwork_services.hide(gone.artwork, actor=None)
    response = checkout(login_client(customer))
    assert response.status_code == 409 and list(response.json()["error"]["details"]["items"].values()) == [
        "artwork_unavailable"
    ]
    ok.refresh_from_db()
    assert ok.quantity_reserved == 0 and not Order.objects.exists()


def test_pending_limit_and_duplicate_reservation(login_client, customer, offer):
    settings = SiteSetting.load()
    settings.max_pending_orders_per_user = 1
    settings.save()
    client = login_client(customer)
    fill_cart(customer, (offer(), 1))
    assert checkout(client).status_code == 201
    fill_cart(customer, (offer(), 1))
    assert checkout(client).json()["error"]["code"] == "PENDING_ORDERS_LIMIT"


@pytest.mark.django_db(transaction=True)
def test_two_customers_racing_for_one_piece(make_user, offer):
    """Both have it in their cart; exactly one checkout wins (BR-206, BR-325)."""
    listing = offer()
    buyers = [make_user(), make_user()]
    for buyer in buyers:
        fill_cart(buyer, (listing, 1))
    results, barrier = [], threading.Barrier(2)

    def go(buyer):
        barrier.wait()
        try:
            services.checkout(
                user=buyer,
                policy_version=policy.current_version(),
                contact={"contact_name": "x", "contact_phone": buyer.phone},
            )
            results.append("ok")
        except services.CheckoutError:
            results.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=go, args=(b,)) for b in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "refused"] and Order.objects.count() == 1


# --- expiry (BR-307/308/309) ------------------------------------------------------------------------------
def test_expiry_releases_stock_and_blocks_late_deposits(customer, offer, ops):
    with freeze_time("2026-11-05 10:00:00"):
        order, listing = order_with(customer, offer)
    with freeze_time("2026-11-06 10:00:01"):
        with pytest.raises(services.OrderExpiredError):
            pay(order, ops, "deposit", "300.00")
        order.refresh_from_db()
        assert order.status == OrderStatus.EXPIRED  # committed even though the payment was refused
        listing.refresh_from_db()
        assert (listing.quantity_available, listing.quantity_reserved) == (1, 0)
        assert order.history.last().actor is None


def test_beat_task_expires_due_orders(customer, offer):
    with freeze_time("2026-11-05 10:00:00"):
        order, _ = order_with(customer, offer)
    with freeze_time("2026-11-06 11:00:00"):
        assert services.expire_due_orders() == 1
    order.refresh_from_db()
    assert order.status == OrderStatus.EXPIRED


# --- customer cancellation (Q9) ------------------------------------------------------------------------------
def test_customer_cancels_before_deposit_only(login_client, customer, offer, ops):
    order, listing = order_with(customer, offer)
    client = login_client(customer)
    response = client.post(f"/api/v1/orders/{order.order_number}/cancel", {"reason": "غيرت رأيي"})
    assert response.json()["status"] == "cancelled_by_customer"
    listing.refresh_from_db()
    assert listing.quantity_available == 1

    paid, _ = order_with(customer, offer)
    pay(paid, ops, "deposit", "300.00")
    assert client.post(f"/api/v1/orders/{paid.order_number}/cancel").status_code == 409


def test_customers_see_only_their_orders(login_client, customer, make_user, offer):
    order, _ = order_with(customer, offer)
    assert login_client(make_user()).get(f"/api/v1/orders/{order.order_number}").status_code == 404
    mine = login_client(customer).get("/api/v1/orders").json()["results"]
    assert [o["number"] for o in mine] == [order.order_number] and mine[0]["needs_action"] is True


def test_whatsapp_link_only_when_configured(login_client, customer, offer):
    order, _ = order_with(customer, offer)
    client = login_client(customer)
    assert client.get(f"/api/v1/orders/{order.order_number}").json()["whatsapp_url"] is None
    settings = SiteSetting.load()
    settings.whatsapp_number = "+963 944 000 111"
    settings.save()
    url = client.get(f"/api/v1/orders/{order.order_number}").json()["whatsapp_url"]
    assert url.startswith("https://wa.me/963944000111?text=") and order.order_number in __import__(
        "urllib.parse"
    ).parse.unquote(url)


# --- payments and automatic progress (BR-401…408, §3.1) ----------------------------------------------------
def test_money_drives_the_status(customer, offer, ops):
    order, listing = order_with(customer, offer, price="1000.00")
    pay(order, ops, "deposit", "300.00")
    order.refresh_from_db()
    assert order.status == OrderStatus.DEPOSIT_CONFIRMED and order.deposit_status == "confirmed"
    pay(order, ops, "payment", "200.00")
    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_PENDING and order.payment_status == "partially_paid"
    with pytest.raises(services.ConflictError):
        pay(order, ops, "payment", "600.00")  # more than the remaining 500
    pay(order, ops, "payment", "500.00")
    order.refresh_from_db()
    listing.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED and order.payment_status == "paid" and order.confirmed_at
    assert listing.status == "sold_out" and listing.quantity_sold == 1
    assert [h.to_status for h in order.history.all()] == [
        "pending_deposit",
        "deposit_confirmed",
        "payment_pending",
        "confirmed",
    ]


def test_unconfirmed_records_can_be_confirmed_or_voided_but_confirmed_never(customer, offer, ops):
    order, _ = order_with(customer, offer)
    record = pay(order, ops, "deposit", "300.00", confirm=False)
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING_DEPOSIT
    services.confirm_payment(record, actor=ops)
    with pytest.raises(services.OrderStateError):
        services.void_payment(record, actor=ops, reason="خطأ")
    draft = pay(order, ops, "payment", "50.00", confirm=False)
    services.void_payment(draft, actor=ops, reason="مكرر")
    order.refresh_from_db()
    assert order.amount_paid == Decimal("300.00")


def test_platform_cancellation_after_deposit_is_refund_due(customer, offer, ops):
    order, listing = order_with(customer, offer)
    pay(order, ops, "deposit", "300.00")
    services.cancel_by_platform(order, actor=ops, reason="تلف القطعة")
    order.refresh_from_db()
    listing.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED_BY_PLATFORM and order.deposit_status == "refund_due"
    assert listing.quantity_available == 1
    with pytest.raises(services.ConflictError):
        pay(order, ops, "refund", "400.00")
    pay(order, ops, "refund", "300.00")
    order.refresh_from_db()
    assert order.deposit_status == "refunded" and order.payment_status == "refunded"


def test_customer_withdrawal_after_deposit_forfeits_it(customer, offer, ops):
    order, _ = order_with(customer, offer)
    pay(order, ops, "deposit", "300.00")
    with pytest.raises(services.ConflictError):
        services.cancel_for_customer(order, actor=ops, reason=" ")
    services.cancel_for_customer(order, actor=ops, reason="طلب العميل")
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED_BY_CUSTOMER and order.deposit_status == "forfeited"


def test_confirmed_sale_cancelled_by_platform_returns_stock(customer, offer, ops):
    order, listing = order_with(customer, offer, price="500.00")
    pay(order, ops, "deposit", "150.00")
    pay(order, ops, "payment", "350.00")
    services.cancel_by_platform(order, actor=ops, reason="خطأ في التوثيق")
    listing.refresh_from_db()
    assert listing.status == "active" and (listing.quantity_available, listing.quantity_sold) == (1, 0)


def test_removing_an_item_recomputes_totals(customer, offer, ops):
    a, b = offer(price="100.00"), offer(price="300.00")
    fill_cart(customer, (a, 1), (b, 1))
    order = services.checkout(
        user=customer, policy_version=policy.current_version(), contact={"contact_name": "x", "contact_phone": "1"}
    )
    item = order.items.get(listing=b)
    services.remove_item(order, item, actor=ops, reason="غير متوفر فعلياً")
    order.refresh_from_db()
    b.refresh_from_db()
    assert (order.subtotal, order.deposit_due) == (Decimal("100.00"), Decimal("30.00"))
    assert b.quantity_available == 1
    with pytest.raises(services.OrderStateError):
        services.remove_item(order, order.items.get(listing=a), actor=ops, reason="x")


def test_delivery_then_complete(customer, offer, ops):
    order, _ = order_with(customer, offer, price="500.00")
    with pytest.raises(services.OrderStateError):
        services.update_delivery(order, actor=ops, data={"status": "in_transit"})
    pay(order, ops, "deposit", "150.00")
    pay(order, ops, "payment", "350.00")
    with pytest.raises(services.OrderStateError):
        services.complete(order, actor=ops)
    delivery = services.update_delivery(order, actor=ops, data={"method": "courier", "status": "delivered"})
    assert delivery.delivered_at is not None
    services.complete(order, actor=ops)
    order.refresh_from_db()
    assert order.status == OrderStatus.COMPLETED and order.closed_at


# --- staff API & permissions -----------------------------------------------------------------------------------
def test_staff_api_flow(login_client, customer, offer, ops, super_admin):
    order, _ = order_with(customer, offer)
    client = login_client(ops)
    listed = client.get(f"{ADMIN}?status=pending_deposit&search={order.order_number[-6:]}").json()["results"]
    assert [o["number"] for o in listed] == [order.order_number]
    url = f"{ADMIN}/{order.order_number}"
    detail = client.get(url).json()
    assert detail["actions"]["custom_deposit"] is False and detail["actions"]["record_payment"] is True
    assert detail["actions"]["record_refund"] is False
    assert client.post(f"{url}/deposit", {"amount": "100", "reason": "اتفاق"}).status_code == 403
    custom = login_client(super_admin).post(f"{url}/deposit", {"amount": "100", "reason": "اتفاق"})
    assert custom.status_code == 200 and custom.json()["deposit_due"] == "100.00"

    paid = client.post(
        f"{url}/payments",
        {"kind": "deposit", "amount": "100", "method": "bank_transfer", "reference": "TX-1"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="pay-attempt-1",
    )
    assert paid.status_code == 201 and paid.json()["status"] == "deposit_confirmed"
    replay = client.post(
        f"{url}/payments",
        {"kind": "deposit", "amount": "100", "method": "bank_transfer"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="pay-attempt-1",
    )
    assert replay.status_code == 201 and len(replay.json()["payments"]) == 1  # not recorded twice
    assert client.patch(url, {"internal_notes": "اتصل الساعة 5"}).json()["internal_notes"] == "اتصل الساعة 5"
    assert AuditLog.objects.filter(action="payment.confirmed").exists()


@pytest.mark.parametrize("roles", [None, [], ["content_staff"]])  # auction managers: auction orders only
def test_order_admin_requires_operations_role(roles, api_client, login_client, make_user):
    client = api_client if roles is None else login_client(make_user(roles=roles))
    assert client.get(ADMIN).status_code == 403


def test_staff_cannot_check_out(login_client, ops):
    assert checkout(login_client(ops)).status_code == 403


def test_order_list_lazily_expires(login_client, customer, offer, ops):
    with freeze_time("2026-11-05 10:00:00"):
        order, _ = order_with(customer, offer)
    with freeze_time("2026-11-07 10:00:00"):
        body = login_client(ops).get(f"{ADMIN}?status=pending_deposit").json()
        assert body["results"] == []
    order.refresh_from_db()
    assert order.status == OrderStatus.EXPIRED

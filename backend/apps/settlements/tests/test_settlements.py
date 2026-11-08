import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.artists import services as artist_services
from apps.audit.models import AuditLog
from apps.cart import services as cart_services
from apps.orders import policy
from apps.orders import services as order_services
from apps.orders.models import OrderStatus
from apps.settlements.models import Settlement, SettlementStatus

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/settlements"


@pytest.fixture
def ops(make_user):
    return make_user(roles=["operations_staff"], display_name="عمليات")


@pytest.fixture
def sell(artwork_factory, listing_factory, customer, ops):
    """Places and fully pays an order for one or more new artworks; returns the order."""

    def _sell(*prices, artist=..., confirm=True, **artwork_kw):
        for price in prices:
            kwargs = {} if artist is ... else {"artist": artist}
            listing = listing_factory(artwork_factory(published=True, **kwargs, **artwork_kw), price=price)
            cart_services.add_item(customer, listing=listing, quantity=1)
        order = order_services.checkout(
            user=customer,
            policy_version=policy.current_version(),
            contact={"contact_name": "x", "contact_phone": customer.phone},
        )
        if confirm:
            order_services.record_payment(
                order, actor=ops, kind="payment", amount=order.subtotal, method="cash", confirm=True
            )
            order.refresh_from_db()
        return order

    return _sell


def pay_api(client, ids, reference="HW-77", key=None, **extra):
    return client.post(
        f"{ADMIN}/pay",
        {"settlements": [str(i) for i in ids], "reference": reference, **extra},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex,
    )


def test_confirming_an_order_creates_one_settlement_per_item_from_the_snapshot(sell):
    order = sell("500.00", "200.00")
    assert order.status == OrderStatus.CONFIRMED
    rows = list(Settlement.objects.order_by("gross_amount"))
    assert [(r.gross_amount, r.platform_commission, r.payee_amount) for r in rows] == [
        (Decimal("200.00"), Decimal("30.00"), Decimal("170.00")),
        (Decimal("500.00"), Decimal("75.00"), Decimal("425.00")),  # BR-702 example: 15% default
    ]
    assert all(r.status == SettlementStatus.PENDING and r.payee_type == "artist" for r in rows)
    # Idempotent: replaying the hook adds nothing.
    from apps.settlements import services

    assert services.create_for_order(order) == []


def test_no_settlement_before_confirmation(sell):
    sell("500.00", confirm=False)
    assert not Settlement.objects.exists()


def test_agreement_rate_applies_to_new_orders_only(sell, artist_factory, super_admin):
    artist = artist_factory()
    first = sell("1000.00", artist=artist)
    artist_services.create_agreement(artist, actor=super_admin, commission_rate=Decimal("10"))
    second = sell("1000.00", artist=artist)
    by_order = {s.order_item.order_id: s for s in Settlement.objects.all()}
    assert by_order[first.pk].platform_commission == Decimal("150.00")  # snapshot kept (BR-703)
    assert by_order[second.pk].platform_commission == Decimal("100.00")
    assert by_order[second.pk].commission_rate == Decimal("10.00")


def test_cancelling_a_confirmed_order_cancels_unpaid_settlements(sell, ops, login_client):
    order = sell("300.00", "100.00")
    paid, pending = Settlement.objects.order_by("-gross_amount")
    pay_api(login_client(ops), [paid.public_id])
    order_services.cancel_by_platform(order, actor=ops, reason="قطعة تالفة")
    pending.refresh_from_db()
    paid.refresh_from_db()
    assert pending.status == SettlementStatus.CANCELLED and "أُلغي الطلب" in pending.status_reason
    assert paid.status == SettlementStatus.PAID
    row = next(
        r for r in login_client(ops).get(f"{ADMIN}?status=paid").json()["results"] if r["id"] == str(paid.public_id)
    )
    assert row["order_cancelled_after_payment"] is True


def test_pay_one_payee_with_reference(sell, artist_factory, ops, login_client):
    artist = artist_factory(name="فاتح")
    sell("400.00", "100.00", artist=artist)
    ids = list(Settlement.objects.values_list("public_id", flat=True))
    client = login_client(ops)
    payees = client.get(f"{ADMIN}/payees").json()
    assert payees == [
        {
            "payee_key": f"artist:{artist.pk}",
            "payee_name": "فاتح",
            "payee_type": "artist",
            "count": 2,
            "amount": "425.00",
            "oldest": payees[0]["oldest"],
        }
    ]
    assert pay_api(client, ids, reference=" ").status_code == 400
    future = (timezone.localdate() + timedelta(days=1)).isoformat()
    assert pay_api(client, ids, paid_at=future).status_code == 400
    response = pay_api(client, ids, notes="حوالة الهرم")
    assert response.status_code == 200 and {r["status"] for r in response.json()} == {"paid"}
    assert all(r["reference"] == "HW-77" and r["paid_by"] == "عمليات" for r in response.json())
    assert AuditLog.objects.filter(action="settlement.paid").count() == 2
    assert pay_api(client, ids).status_code == 409  # already paid
    summary = client.get(f"{ADMIN}/summary").json()
    assert summary["pending"] == {"count": 0, "amount": "0.00"}
    assert summary["paid_this_month"] == {"count": 2, "amount": "425.00"}


def test_one_transfer_cannot_mix_payees(sell, artist_factory, ops, login_client):
    sell("100.00", artist=artist_factory())
    sell("100.00", artist=artist_factory())
    ids = list(Settlement.objects.values_list("public_id", flat=True))
    response = pay_api(login_client(ops), ids)
    assert response.status_code == 400 and "settlements" in response.json()["error"]["details"]
    assert not Settlement.objects.filter(status="paid").exists()


def test_pay_retry_with_same_key_is_idempotent(sell, ops, login_client):
    sell("100.00")
    s = Settlement.objects.get()
    client = login_client(ops)
    first = pay_api(client, [s.public_id], key="pay-key-12345")
    again = pay_api(client, [s.public_id], key="pay-key-12345")
    assert first.status_code == again.status_code == 200 and first.json() == again.json()


def test_hold_release_cancel_need_reasons(sell, ops, login_client):
    sell("100.00")
    s = Settlement.objects.get()
    client = login_client(ops)
    base = f"{ADMIN}/{s.public_id}"
    assert client.post(f"{base}/hold", {"reason": ""}, format="json").status_code == 400
    held = client.post(f"{base}/hold", {"reason": "بانتظار تأكيد حساب الفنان"}, format="json").json()
    assert held["status"] == "on_hold" and held["actions"] == ["release", "cancel"]
    assert pay_api(client, [s.public_id]).status_code == 409  # held items are not paid
    assert client.post(f"{base}/release").json()["actions"] == ["pay", "hold", "cancel"]
    cancelled = client.post(f"{base}/cancel", {"reason": "اتفاق مع الفنان"}, format="json").json()
    assert cancelled["status"] == "cancelled" and cancelled["actions"] == []


def test_owner_is_paid_for_auction_request_works(sell, make_user):
    owner = make_user(display_name="مالكة اللوحة")
    order = sell("1000.00", artist=None, creator_name_override="فنان قديم", owner_user=owner, confirm=False)
    item = order.items.get()
    item.payee_type_snapshot = "owner"
    item.save()
    from apps.settlements import services

    s = services.create_for_order(order)[0]
    assert s.payee_type == "owner" and s.owner_user == owner and s.payee_name == "مالكة اللوحة"
    assert s.payee_key == f"owner:{owner.pk}"


@pytest.mark.parametrize("roles", [[], ["content_staff"], ["auction_manager"]])
def test_settlements_are_for_operations_and_super_admin(roles, make_user, login_client):
    client = login_client(make_user(roles=roles))
    assert client.get(ADMIN).status_code == 403
    assert client.get(f"{ADMIN}/summary").status_code == 403

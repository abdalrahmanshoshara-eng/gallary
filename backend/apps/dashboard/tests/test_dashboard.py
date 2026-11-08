import pytest

from apps.audit import services as audit

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/dashboard"


def test_sections_follow_roles(make_user, login_client):
    expect = {
        "content_staff": {"catalog"},
        "operations_staff": {"orders", "settlements"},
        "auction_manager": {"auctions"},
        "super_admin": {"catalog", "orders", "settlements", "auctions"},
    }
    for role, sections in expect.items():
        body = login_client(make_user(roles=[role])).get(URL).json()
        shown = {k for k in ("catalog", "orders", "settlements", "auctions") if body[k] is not None}
        assert shown == sections, role


def test_customers_and_visitors_are_refused(customer, login_client, api_client):
    assert login_client(customer).get(URL).status_code == 403
    assert api_client.get(URL).status_code in (401, 403)


def test_kpis_count_sales_and_commission(
    super_admin, login_client, artwork_factory, listing_factory, customer, make_user
):
    from apps.cart import services as cart_services
    from apps.orders import policy
    from apps.orders import services as order_services

    ops = make_user(roles=["operations_staff"])
    sold = listing_factory(artwork_factory(published=True), price="1000.00")
    listing_factory(artwork_factory(published=True), price="50.00")
    cart_services.add_item(customer, listing=sold, quantity=1)
    order = order_services.checkout(
        user=customer,
        policy_version=policy.current_version(),
        contact={"contact_name": "x", "contact_phone": customer.phone},
    )
    order_services.record_payment(order, actor=ops, kind="payment", amount=order.subtotal, method="cash")
    body = login_client(super_admin).get(f"{URL}?period=all").json()
    assert body["period"] == "all"
    assert body["catalog"] == {"published_artworks": 2, "available_artworks": 1}
    assert body["orders"]["sales_count"] == 1 and body["orders"]["sales_amount"] == "1000.00"
    assert body["orders"]["commission_amount"] == "150.00"
    assert body["settlements"] == {"pending_count": 1, "pending_amount": "850.00"}


def test_audit_log_is_super_admin_only_and_filterable(super_admin, content_staff, login_client):
    audit.record(
        actor=super_admin, action="settlement.paid", entity_type="settlements.settlement", entity_id="s1", reason="HW-1"
    )
    audit.record(actor=None, action="order.expired", entity_type="orders.order", entity_id="ART-1")
    client = login_client(super_admin)
    assert login_client(content_staff).get("/api/v1/admin/audit").status_code == 403
    rows = client.get("/api/v1/admin/audit?action=settlement.").json()["results"]
    assert [r["entity_id"] for r in rows] == ["s1"] and rows[0]["actor"] == super_admin.display_name
    system = client.get("/api/v1/admin/audit?system=1").json()["results"]
    assert all(r["actor"] is None for r in system) and any(r["entity_id"] == "ART-1" for r in system)
    facets = client.get("/api/v1/admin/audit/facets").json()["entity_types"]
    assert {"orders.order", "settlements.settlement"} <= set(facets)

from decimal import Decimal

import pytest

from apps.artworks import services as artwork_services
from apps.cart import services
from apps.listings import services as listing_services
from apps.listings.models import Listing

pytestmark = pytest.mark.django_db
CART = "/api/v1/cart"


@pytest.fixture
def offer(artwork_factory, listing_factory):
    def _make(**kw):
        return listing_factory(artwork_factory(published=True), **kw)

    return _make


def add(client, listing, quantity=1):
    return client.post(f"{CART}/items", {"listing": str(listing.public_id), "quantity": quantity})


def test_customer_adds_updates_and_removes(login_client, customer, offer):
    client = login_client(customer)
    unique = offer(price="300.00")
    limited = offer(price="50.00", quantity_mode="limited", quantity_total=5, max_per_order=3)
    assert add(client, unique).status_code == 201
    body = add(client, limited, 2).json()
    assert body["count"] == 2 and body["subtotal"] == "400.00" and body["can_checkout"] is True
    assert body["deposit_due"] == "120.00"  # default 30% of each line
    line = next(x for x in body["lines"] if x["quantity_mode"] == "limited")
    assert line["max_quantity"] == 3 and line["line_total"] == "100.00"

    assert add(client, limited, 3).json()["count"] == 2  # same offer: quantity updated, no duplicate
    updated = client.patch(f"{CART}/items/{line['id']}", {"quantity": 1}).json()
    assert next(x for x in updated["lines"] if x["id"] == line["id"])["quantity"] == 1
    assert client.delete(f"{CART}/items/{line['id']}").json()["count"] == 1
    assert client.get(f"{CART}/count").json() == {"count": 1}


def test_quantity_rules(login_client, customer, offer):
    client = login_client(customer)
    unique = offer()
    limited = offer(quantity_mode="limited", quantity_total=3, max_per_order=2)
    assert add(client, unique, 2).json()["error"]["details"]["reason"] == "quantity_limit"
    response = add(client, limited, 3)
    assert response.status_code == 409 and response.json()["error"]["details"]["max_quantity"] == 2


def test_cart_does_not_reserve_stock(login_client, customer, offer):
    listing = offer()
    add(login_client(customer), listing)
    listing.refresh_from_db()
    assert (listing.quantity_available, listing.quantity_reserved) == (1, 0)


def test_auctions_and_unavailable_offers_are_refused(login_client, customer, offer, artwork_factory):
    client = login_client(customer)
    auction = Listing.objects.create(artwork=artwork_factory(published=True), sale_mode="auction", quantity_total=1)
    assert add(client, auction).json()["error"]["details"]["reason"] == "auction_only"
    draft = listing_services.create_listing(actor=None, artwork=artwork_factory(published=True))
    assert add(client, draft).status_code == 409


def test_price_change_and_unavailability_block_checkout(login_client, customer, offer):
    client = login_client(customer)
    priced = offer(price="100.00")
    hidden = offer(price="200.00")
    add(client, priced)
    add(client, hidden)
    listing_services.set_pricing(
        priced,
        actor=None,
        price_usd=Decimal("120.00"),
        commission_rate_override=None,
        deposit_type="",
        deposit_value=None,
    )
    artwork_services.hide(hidden.artwork, actor=None)

    body = client.get(CART).json()
    assert set(body["blocking"]) == {"price_changed", "unavailable"} and body["can_checkout"] is False
    changed = next(x for x in body["lines"] if x["price_changed"])
    assert (changed["price_at_add"], changed["unit_price"]) == ("100.00", "120.00")
    assert next(x for x in body["lines"] if x["problem"])["problem"] == "artwork_unavailable"
    assert body["subtotal"] == "120.00"  # unavailable lines are excluded from totals

    accepted = client.post(f"{CART}/accept-prices").json()
    assert accepted["blocking"] == ["unavailable"]


def test_cart_limit(login_client, customer, offer, monkeypatch):
    monkeypatch.setattr(services, "MAX_ITEMS", 2)
    client = login_client(customer)
    add(client, offer())
    add(client, offer())
    response = add(client, offer())
    assert response.status_code == 409 and response.json()["error"]["code"] == "CART_FULL"


def test_lines_are_private(login_client, customer, make_user, offer):
    line_id = add(login_client(customer), offer()).json()["lines"][0]["id"]
    intruder = login_client(make_user())
    assert intruder.patch(f"{CART}/items/{line_id}", {"quantity": 1}).status_code == 404
    assert intruder.delete(f"{CART}/items/{line_id}").status_code == 404


@pytest.mark.parametrize("roles", [None, ["content_staff"], ["super_admin"]])
def test_cart_is_for_customers_only(roles, api_client, login_client, make_user, offer):
    client = api_client if roles is None else login_client(make_user(roles=roles))
    assert client.get(CART).status_code == 403
    assert add(client, offer()).status_code == 403

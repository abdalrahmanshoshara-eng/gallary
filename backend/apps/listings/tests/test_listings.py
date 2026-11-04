import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.catalog.models import Material, Technique
from apps.core.errors import ConflictError
from apps.core.models import SiteSetting
from apps.listings import services
from apps.listings.models import Listing, ListingStatus

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin"


def price(listing, value="500.00", **kw):
    return services.set_pricing(
        listing,
        actor=None,
        price_usd=Decimal(value),
        commission_rate_override=kw.get("commission"),
        deposit_type=kw.get("deposit_type", ""),
        deposit_value=kw.get("deposit_value"),
    )


# --- lifecycle and pricing (BR-202, BR-208, BR-212) -------------------------------------------
def test_offer_cannot_activate_before_pricing_and_publication(artwork_factory):
    draft_artwork = artwork_factory()
    listing = services.create_listing(actor=None, artwork=draft_artwork)
    with pytest.raises(services.ActivationError) as exc:
        services.activate(listing, actor=None)
    assert exc.value.details["problems"] == ["pricing_not_approved", "artwork_not_public"]
    price(listing)
    with pytest.raises(services.ActivationError):
        services.activate(listing, actor=None)


def test_database_refuses_an_active_offer_without_pricing(artwork_factory):
    listing = services.create_listing(actor=None, artwork=artwork_factory(published=True))
    with pytest.raises(IntegrityError), transaction.atomic():
        Listing.objects.filter(pk=listing.pk).update(status=ListingStatus.ACTIVE)


def test_one_active_offer_per_artwork(artwork_factory, listing_factory):
    artwork = artwork_factory(published=True)
    listing_factory(artwork)
    second = listing_factory(artwork, active=False)
    with pytest.raises(services.AlreadyActiveError):
        services.activate(second, actor=None)


def test_effective_commission_and_deposit_fall_back_to_settings(artwork_factory, listing_factory):
    settings = SiteSetting.load()
    settings.default_commission_rate = Decimal("12.50")
    settings.save()
    listing = listing_factory(artwork_factory(published=True), price="400.00")
    assert services.commission_rate(listing) == Decimal("12.50")
    assert services.deposit_terms(listing).type == "percentage"
    price(listing, "400.00", commission=Decimal("20"), deposit_type="fixed", deposit_value=Decimal("100"))
    listing.refresh_from_db()
    assert services.commission_rate(listing) == Decimal("20")
    assert services.deposit_terms(listing).amount_for(Decimal("400.00")) == Decimal("100")
    assert services.split_commission(Decimal("500"), Decimal("15")) == (Decimal("75.00"), Decimal("425.00"))


def test_pricing_validation(artwork_factory):
    listing = services.create_listing(actor=None, artwork=artwork_factory(published=True))
    with pytest.raises(ConflictError) as exc:
        price(listing, "100.00", deposit_type="fixed", deposit_value=Decimal("150"))
    assert "deposit_value" in exc.value.details
    with pytest.raises(ConflictError):
        price(listing, "100.00", deposit_type="percentage", deposit_value=Decimal("120"))
    with pytest.raises(ConflictError):
        price(listing, "0")


def test_pricing_change_is_audited(artwork_factory, listing_factory):
    listing = listing_factory(artwork_factory(published=True), price="500.00")
    price(listing, "650.00")
    entry = AuditLog.objects.filter(action="listing.pricing_approved").order_by("created_at").last()
    assert entry.changes["price_usd"] == {"from": "500.00", "to": "650.00"}


# --- inventory (BR-204…208) ------------------------------------------------------------------------
def test_unique_offer_reserve_confirm_sells_out(artwork_factory, listing_factory):
    listing = listing_factory(artwork_factory(published=True))
    with transaction.atomic():
        services.reserve(listing.pk, 1)
    listing.refresh_from_db()
    assert (listing.quantity_available, listing.quantity_reserved) == (0, 1)
    assert services.purchase_problem(listing) == "reserved"
    with transaction.atomic():
        services.confirm_sale(listing.pk, 1)
    listing.refresh_from_db()
    assert listing.status == ListingStatus.SOLD_OUT and listing.quantity_sold == 1


def test_release_reopens_stock(artwork_factory, listing_factory):
    listing = listing_factory(
        artwork_factory(published=True), quantity_mode="limited", quantity_total=3, max_per_order=3
    )
    with transaction.atomic():
        services.reserve(listing.pk, 3)
        services.release(listing.pk, 2)
    listing.refresh_from_db()
    assert (listing.quantity_available, listing.quantity_reserved, listing.status) == (2, 1, "active")
    with pytest.raises(services.InsufficientStockError), transaction.atomic():
        services.reserve(listing.pk, 3)


def test_unlimited_tracks_only_statistics(artwork_factory, listing_factory):
    listing = listing_factory(artwork_factory(published=True), quantity_mode="unlimited", max_per_order=5)
    with transaction.atomic():
        services.reserve(listing.pk, 5)
        services.confirm_sale(listing.pk, 5)
    listing.refresh_from_db()
    assert listing.status == "active" and listing.quantity_sold == 5 and listing.quantity_total is None


def test_max_per_order_and_window(artwork_factory, listing_factory):
    listing = listing_factory(
        artwork_factory(published=True), quantity_mode="limited", quantity_total=5, max_per_order=2
    )
    assert services.purchase_problem(listing, 3) == "quantity_limit"
    future = listing_factory(
        artwork_factory(published=True), starts_at=timezone.now() + timedelta(days=1), ends_at=None
    )
    assert services.purchase_problem(future) == "not_started"


def test_hidden_artwork_offer_is_not_purchasable(artwork_factory, listing_factory):
    from apps.artworks import services as artwork_services

    artwork = artwork_factory(published=True)
    listing = listing_factory(artwork)
    artwork_services.hide(artwork, actor=None)
    listing.refresh_from_db()
    assert services.purchase_problem(listing) == "artwork_unavailable"
    with pytest.raises(services.NotPurchasableError), transaction.atomic():
        services.reserve(listing.pk, 1)


def test_limited_total_cannot_drop_below_committed(artwork_factory, listing_factory):
    listing = listing_factory(
        artwork_factory(published=True), quantity_mode="limited", quantity_total=5, max_per_order=5
    )
    with transaction.atomic():
        services.reserve(listing.pk, 3)
    with pytest.raises(ConflictError):
        services.update_listing(listing, actor=None, data={"quantity_total": 2})
    listing = services.update_listing(listing, actor=None, data={"quantity_total": 8})
    assert (listing.quantity_total, listing.quantity_available) == (8, 5)


def test_expired_offers_end(artwork_factory, listing_factory):
    listing = listing_factory(artwork_factory(published=True), ends_at=timezone.now() + timedelta(minutes=5))
    assert services.end_expired_listings(now=timezone.now() + timedelta(minutes=6)) == 1
    listing.refresh_from_db()
    assert listing.status == ListingStatus.ENDED


@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations_never_oversell(artwork_factory, listing_factory):
    """Ten buyers race for 3 units: exactly 3 reservations succeed (BR-206)."""
    listing = listing_factory(artwork_factory(published=True), quantity_mode="limited", quantity_total=3)
    results, barrier = [], threading.Barrier(10)

    def buyer():
        barrier.wait()
        try:
            with transaction.atomic():
                services.reserve(listing.pk, 1)
            results.append("ok")
        except services.InsufficientStockError:
            results.append("sold_out")
        finally:
            connection.close()

    threads = [threading.Thread(target=buyer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    listing.refresh_from_db()
    assert results.count("ok") == 3 and results.count("sold_out") == 7
    assert (listing.quantity_available, listing.quantity_reserved) == (0, 3)


# --- API & permissions ------------------------------------------------------------------------------
def test_editor_creates_offer_but_only_super_admin_prices_it(login_client, content_staff, super_admin, artwork_factory):
    artwork = artwork_factory(published=True)
    editor = login_client(content_staff)
    created = editor.post(
        f"{ADMIN}/artworks/{artwork.public_id}/listings", {"quantity_mode": "limited", "quantity_total": 4}
    )
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["status"] == "draft" and body["activation_problems"] == ["pricing_not_approved"]
    url = f"{ADMIN}/listings/{body['id']}"

    assert editor.post(f"{url}/pricing", {"price_usd": "300"}).status_code == 403
    assert editor.post(f"{url}/activate").status_code == 409

    priced = login_client(super_admin).post(
        f"{url}/pricing", {"price_usd": "300", "deposit_type": "fixed", "deposit_value": "50"}, format="json"
    )
    assert priced.status_code == 200, priced.json()
    assert priced.json()["effective_deposit"] == {"type": "fixed", "value": "50.00", "inherited": False}
    activated = editor.post(f"{url}/activate")
    assert activated.status_code == 200 and activated.json()["status"] == "active"
    assert editor.delete(url).status_code == 409  # activated offers are withdrawn, not deleted
    assert editor.post(f"{url}/withdraw", {"reason": "اتفاق جديد"}).json()["status"] == "withdrawn"


@pytest.mark.parametrize("roles", [None, [], ["operations_staff"]])
def test_listing_admin_requires_catalog_role(roles, make_user, login_client, api_client, artwork_factory):
    client = api_client if roles is None else login_client(make_user(roles=roles))
    artwork = artwork_factory(published=True)
    assert client.get(f"{ADMIN}/artworks/{artwork.public_id}/listings").status_code == 403


def test_settings_read_by_staff_written_by_super_admin(login_client, content_staff, super_admin):
    assert login_client(content_staff).get(f"{ADMIN}/settings").status_code == 200
    assert login_client(content_staff).patch(f"{ADMIN}/settings", {"default_commission_rate": "10"}).status_code == 403
    admin = login_client(super_admin)
    bad = admin.patch(f"{ADMIN}/settings", {"default_deposit_type": "percentage", "default_deposit_value": "150"})
    assert bad.status_code == 400
    ok = admin.patch(f"{ADMIN}/settings", {"default_commission_rate": "10.00", "whatsapp_number": "+963944000111"})
    assert ok.status_code == 200 and ok.json()["default_commission_rate"] == "10.00"
    assert AuditLog.objects.filter(action="settings.updated").exists()


# --- storefront: offers, search, filters (§21) ---------------------------------------------------
def slugs(client, query=""):
    return [a["slug"] for a in client.get(f"/api/v1/artworks{query}").json()["results"]]


def test_cards_and_detail_show_the_offer(api_client, artwork_factory, listing_factory):
    artwork = artwork_factory(published=True)
    listing_factory(artwork, price="750.00", quantity_mode="limited", quantity_total=3, max_per_order=2)
    card = api_client.get("/api/v1/artworks").json()["results"][0]
    assert card["offer"]["price_usd"] == "750.00" and card["offer"]["available"] == 3
    assert card["offer"]["purchasable"] is True and card["offer"]["unavailable_reason"] is None
    detail = api_client.get(f"/api/v1/artworks/{artwork.slug}").json()
    assert detail["offer"]["max_per_order"] == 2
    assert "commission_rate_override" not in detail["offer"] and "internal_notes" not in detail["offer"]
    no_offer = artwork_factory(published=True)
    assert api_client.get(f"/api/v1/artworks/{no_offer.slug}").json()["offer"] is None


def test_arabic_search_tolerates_spelling_variants(api_client, artwork_factory, artist_factory):
    artwork_factory(published=True, slug="a", title="إطلالة على الجامع الأموي", artist=artist_factory(name="مصطفى علي"))
    artwork_factory(published=True, slug="b", title="سوق الحميدية", description="لوحة زيتية مُفعمة بالحياة")
    artwork_factory(slug="draft", title="اطلالة سرية")  # unpublished: never found
    assert slugs(api_client, "?q=اطلاله") == ["a"]
    assert slugs(api_client, "?q=مصطفي") == ["a"]
    assert slugs(api_client, "?q=مفعمه") == ["b"]
    assert slugs(api_client, "?q=سوق الحميديه") == ["b"]
    assert slugs(api_client, "?q=سوق الأموي") == []  # all words must match


def test_search_covers_category_materials_and_techniques(
    api_client, artwork_factory, django_capture_on_commit_callbacks
):
    from apps.artworks import services as artwork_services

    artwork = artwork_factory(published=True, slug="wood")
    artwork_services.update_artwork(
        artwork,
        actor=None,
        data={
            "materials": [Material.objects.get(slug="wood").pk],
            "techniques": [Technique.objects.get(slug="oil").pk],
        },
    )
    artwork_factory(published=True, slug="other")
    assert slugs(api_client, "?q=خشب") == ["wood"]
    assert slugs(api_client, "?q=زيت") == ["wood"]
    assert set(slugs(api_client, "?q=لوحات")) == {"wood", "other"}  # category name


def test_renaming_an_artist_reindexes_their_artworks(
    api_client, artwork_factory, artist_factory, django_capture_on_commit_callbacks
):
    artist = artist_factory(name="اسم قديم")
    artwork_factory(published=True, slug="x", artist=artist)
    with django_capture_on_commit_callbacks(execute=True):
        artist.name = "نذير نبعة"
        artist.save()
    assert slugs(api_client, "?q=نبعه") == ["x"]


def test_filters_price_availability_material_and_ordering(api_client, artwork_factory, listing_factory):
    from apps.artworks import services as artwork_services

    cheap = artwork_factory(published=True, slug="cheap")
    listing_factory(cheap, price="100.00")
    pricey = artwork_factory(published=True, slug="pricey")
    listing_factory(pricey, price="900.00")
    artwork_factory(published=True, slug="not-for-sale")
    artwork_services.update_artwork(cheap, actor=None, data={"materials": [Material.objects.get(slug="wood").pk]})

    assert slugs(api_client, "?price_min=200") == ["pricey"]
    assert slugs(api_client, "?price_max=200") == ["cheap"]
    assert set(slugs(api_client, "?availability=available")) == {"cheap", "pricey"}
    assert slugs(api_client, "?availability=unavailable") == ["not-for-sale"]
    assert slugs(api_client, "?material=wood") == ["cheap"]
    assert slugs(api_client, "?sale_mode=fixed_price&ordering=price_desc") == ["pricey", "cheap"]
    assert slugs(api_client, "?ordering=price_asc")[:2] == ["cheap", "pricey"]  # unpriced last
    assert slugs(api_client, "?price_min=abc") != []  # junk input is ignored, not a 500


def test_storefront_query_count_is_constant(
    api_client, artwork_factory, listing_factory, django_assert_max_num_queries
):
    for _ in range(6):
        listing_factory(artwork_factory(published=True))
    with django_assert_max_num_queries(5):
        assert len(api_client.get("/api/v1/artworks?q=عمل&availability=available").json()["results"]) == 6

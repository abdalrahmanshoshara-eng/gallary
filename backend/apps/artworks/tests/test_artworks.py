import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.artists.models import ArtistStatus
from apps.artworks import services
from apps.artworks.models import ArchiveVisibility, Artwork, PublicationStatus
from apps.audit.models import AuditLog
from apps.catalog.models import Category, Material
from apps.media.models import ImageAsset, ImageStatus
from conftest import make_image_bytes

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/artworks"


def upload(name="a.jpg"):
    return SimpleUploadedFile(name, make_image_bytes(), content_type="image/jpeg")


# --- public visibility (one definition, many cases) ----------------------------------------
def public_slugs(client, path="/api/v1/artworks"):
    return {a["slug"] for a in client.get(path).json()["results"]}


def test_visibility_matrix(api_client, artwork_factory, artist_factory):
    shown = artwork_factory(published=True, slug="shown")
    artwork_factory(slug="draft")
    hidden = artwork_factory(published=True, slug="hidden")
    services.hide(hidden, actor=None)
    hidden_artist = artist_factory(status=ArtistStatus.HIDDEN)
    by_hidden_artist = artwork_factory(published=True, slug="by-hidden-artist")
    by_hidden_artist.artist = hidden_artist
    by_hidden_artist.save()
    archived = artwork_factory(published=True, slug="archived")
    services.archive(archived, actor=None)
    archived_hidden = artwork_factory(published=True, slug="archived-hidden")
    services.archive(archived_hidden, actor=None, visibility=ArchiveVisibility.HIDDEN)
    no_artist = artwork_factory(published=False, artist=None, creator_name_override="مجهول", slug="anonymous")
    services.add_image(no_artist, upload(), actor=None)
    ImageAsset.objects.update(status=ImageStatus.READY)
    services.publish(no_artist, actor=None)

    assert public_slugs(api_client) == {"shown", "anonymous"}
    assert public_slugs(api_client, "/api/v1/archive") == {"archived"}
    detail = lambda slug: api_client.get(f"/api/v1/artworks/{slug}").status_code  # noqa: E731
    assert detail(shown.slug) == 200
    assert detail("archived") == 200  # archived works stay viewable (BR-802)
    for slug in ("draft", "hidden", "by-hidden-artist", "archived-hidden"):
        assert detail(slug) == 404, slug


def test_public_detail_payload(api_client, artwork_factory):
    artwork = artwork_factory(
        published=True,
        height_cm="80.00",
        width_cm="60.00",
        year_created=1998,
        internal_notes="لا تُعرض",
        owner_name="مجموعة خاصة",
    )
    artwork.materials.add(Material.objects.get(slug="wood"))
    body = api_client.get(f"/api/v1/artworks/{artwork.slug}").json()
    assert body["dimensions"] == {"height_cm": "80.00", "width_cm": "60.00", "depth_cm": None, "weight_kg": None}
    assert body["materials"] == [{"name": "خشب", "slug": "wood"}]
    assert body["owner_name"] == "مجموعة خاصة"
    assert "internal_notes" not in body and "owner_user_phone" not in body
    assert body["images"][0]["image"]["variants"][0]["url"].startswith("http://media.test/images/")
    assert body["is_archived"] is False and body["category"]["parent"] is None


def test_category_filter_includes_subcategories_and_ordering(api_client, artwork_factory, category):
    sub = Category.objects.create(name="بورتريه", slug="portrait", parent=category)
    a = artwork_factory(published=True, title="ب", slug="b", year_created=2001)
    b = artwork_factory(published=True, title="أ", slug="a", category=sub, year_created=1990)
    artwork_factory(published=True, slug="sculpture", category=Category.objects.get(slug="sculptures"))
    assert public_slugs(api_client, "/api/v1/artworks?category=paintings") == {a.slug, b.slug}
    assert public_slugs(api_client, "/api/v1/artworks?category=portrait") == {b.slug}
    titles = [x["title"] for x in api_client.get("/api/v1/artworks?ordering=title").json()["results"]]
    assert titles[:2] == ["أ", "ب"]
    newest = [x["slug"] for x in api_client.get("/api/v1/artworks").json()["results"]]
    assert newest[0] == "sculpture"


def test_list_query_count_is_constant(api_client, artwork_factory, django_assert_max_num_queries):
    for _ in range(8):
        artwork_factory(published=True)
    with django_assert_max_num_queries(4):  # count + page + primary images (+ savepoint slack)
        assert len(api_client.get("/api/v1/artworks").json()["results"]) == 8


# --- publication rules (BR-102, BR-103) --------------------------------------------------------
def test_publish_requirements(artwork_factory, django_capture_on_commit_callbacks):
    artwork = artwork_factory()
    with pytest.raises(services.PublishRequirementsError) as exc:
        services.publish(artwork, actor=None)
    assert exc.value.details["problems"] == ["primary_image_missing"]

    services.add_image(artwork, upload(), actor=None)  # processing not run yet
    with pytest.raises(services.PublishRequirementsError) as exc:
        services.publish(artwork, actor=None)
    assert exc.value.details["problems"] == ["primary_image_not_ready"]

    ImageAsset.objects.update(status=ImageStatus.READY)
    artwork.artist.status = ArtistStatus.HIDDEN
    artwork.artist.save()
    with pytest.raises(services.PublishRequirementsError) as exc:
        services.publish(artwork, actor=None)
    assert exc.value.details["problems"] == ["artist_hidden"]

    artwork.artist.status = ArtistStatus.ACTIVE
    artwork.artist.save()
    services.publish(artwork, actor=None)
    artwork.refresh_from_db()
    assert artwork.publication_status == PublicationStatus.PUBLISHED and artwork.published_at


def test_hide_and_republish_keep_first_publication_date(artwork_factory):
    artwork = artwork_factory(published=True)
    first = artwork.published_at
    services.hide(artwork, actor=None)
    with pytest.raises(services.InvalidTransitionError):
        services.hide(artwork, actor=None)
    services.publish(artwork, actor=None)
    artwork.refresh_from_db()
    assert artwork.published_at == first


def test_archive_rules(artwork_factory):
    draft = artwork_factory()
    with pytest.raises(services.InvalidTransitionError):
        services.archive(draft, actor=None)
    artwork = artwork_factory(published=True)
    services.archive(artwork, actor=None, reason="بيع خارج المنصة")
    services.unarchive(artwork, actor=None)
    assert [e.action for e in AuditLog.objects.filter(entity_id=str(artwork.public_id)).order_by("created_at")][
        -2:
    ] == [
        "artwork.archived",
        "artwork.unarchived",
    ]


def test_published_artworks_are_never_deleted(artwork_factory):
    artwork = artwork_factory(published=True)
    with pytest.raises(services.ArtworkDeleteError):
        services.delete_artwork(artwork, actor=None)
    services.hide(artwork, actor=None)
    with pytest.raises(services.ArtworkDeleteError):
        services.delete_artwork(artwork, actor=None)


def test_deleting_a_draft_removes_its_images(artwork_factory, django_capture_on_commit_callbacks):
    artwork = artwork_factory()
    with django_capture_on_commit_callbacks(execute=True):
        services.add_image(artwork, upload(), actor=None)
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_artwork(artwork, actor=None)
    assert not Artwork.objects.exists() and not ImageAsset.objects.exists()


# --- images ---------------------------------------------------------------------------------------
def test_images_primary_order_and_deletion(artwork_factory, django_capture_on_commit_callbacks):
    artwork = artwork_factory()
    with django_capture_on_commit_callbacks(execute=True):
        first = services.add_image(artwork, upload(), actor=None)
        second = services.add_image(artwork, upload(), actor=None)
        third = services.add_image(artwork, upload(), actor=None)
    assert first.is_primary and not second.is_primary
    services.reorder_images(artwork, [third.public_id, first.public_id, second.public_id], actor=None)
    assert list(artwork.images.values_list("public_id", flat=True)) == [
        third.public_id,
        first.public_id,
        second.public_id,
    ]
    with pytest.raises(Exception):  # noqa: B017 — incomplete order list
        services.reorder_images(artwork, [third.public_id], actor=None)

    services.update_image(second, actor=None, make_primary=True)
    assert list(artwork.images.filter(is_primary=True)) == [second]
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_image(second, actor=None)
    assert artwork.images.get(is_primary=True) == third  # first in order is promoted


def test_last_image_of_published_artwork_is_protected(artwork_factory):
    artwork = artwork_factory(published=True)
    with pytest.raises(services.LastImageError):
        services.delete_image(artwork.images.get(), actor=None)


# --- staff API ------------------------------------------------------------------------------------
@pytest.mark.parametrize("roles", [None, [], ["operations_staff"], ["auction_manager"]])
def test_admin_artworks_require_catalog_role(roles, make_user, login_client, api_client, category):
    client = api_client if roles is None else login_client(make_user(roles=roles))
    assert client.get(ADMIN).status_code == 403
    assert client.post(ADMIN, {"title": "x", "category": category.pk, "creator_name_override": "y"}).status_code == 403


def test_full_editor_flow_through_the_api(
    login_client, content_staff, artist_factory, category, django_capture_on_commit_callbacks, api_client
):
    client = login_client(content_staff)
    artist = artist_factory()
    created = client.post(
        ADMIN,
        {
            "title": "ياسمين الشام",
            "category": category.pk,
            "artist": str(artist.public_id),
            "materials": [Material.objects.get(slug="wood").pk],
            "height_cm": "50",
            "year_created": 2024,
        },
    )
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["slug"] == "ياسمين-الشام" and body["publish_problems"] == ["primary_image_missing"]
    url = f"{ADMIN}/{body['id']}"

    with django_capture_on_commit_callbacks(execute=True):
        image = client.post(f"{url}/images", {"file": upload(), "alt_text": "لوحة"}, format="multipart")
    assert image.status_code == 201 and image.json()["is_primary"]

    published = client.post(f"{url}/publish")
    assert published.status_code == 200, published.json()
    assert published.json()["publication_status"] == "published"
    assert api_client.get("/api/v1/artworks/ياسمين-الشام").status_code == 200

    archived = client.post(f"{url}/archive", {"visibility": "visible", "reason": "بيعت"})
    assert archived.json()["is_archived"] is True
    assert client.delete(url).status_code == 409


def test_creator_is_required(login_client, content_staff, category):
    response = login_client(content_staff).post(ADMIN, {"title": "x", "category": category.pk})
    assert response.status_code == 400 and "artist" in response.json()["error"]["details"]


def test_publish_errors_are_explained(login_client, content_staff, artwork_factory):
    artwork = artwork_factory()
    response = login_client(content_staff).post(f"{ADMIN}/{artwork.public_id}/publish")
    assert response.status_code == 409
    assert response.json()["error"] == {
        **response.json()["error"],
        "code": "PUBLISH_REQUIREMENTS",
        "details": {"problems": ["primary_image_missing"]},
    }


def test_image_endpoints_are_scoped_to_their_artwork(login_client, content_staff, artwork_factory):
    a = artwork_factory(published=True)
    b = artwork_factory()
    foreign = a.images.get()
    response = login_client(content_staff).delete(f"{ADMIN}/{b.public_id}/images/{foreign.public_id}")
    assert response.status_code == 404

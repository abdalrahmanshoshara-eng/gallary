import pytest

from apps.artists.models import Artist, ArtistStatus
from apps.audit.models import AuditLog
from apps.media.models import ImageAsset

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/artists"
INTERNAL_FIELDS = {"contact_phone", "contact_email", "internal_notes", "status"}


def test_public_list_hides_hidden_artists_and_internal_fields(api_client, artist_factory):
    artist_factory(name="ظاهر", contact_phone="+963944567890", internal_notes="سري")
    artist_factory(name="مخفي", status=ArtistStatus.HIDDEN)
    body = api_client.get("/api/v1/artists").json()
    assert [a["name"] for a in body["results"]] == ["ظاهر"]
    assert not INTERNAL_FIELDS & set(body["results"][0])
    assert api_client.get("/api/v1/artists/" + Artist.objects.get(name="مخفي").slug).status_code == 404


def test_featured_first_and_counts_only_public_artworks(api_client, artist_factory, artwork_factory):
    a = artist_factory(name="أ")
    b = artist_factory(name="ب", is_featured=True)
    artwork_factory(artist=a, published=True)
    artwork_factory(artist=a)  # draft: not counted
    results = api_client.get("/api/v1/artists").json()["results"]
    assert [r["name"] for r in results] == ["ب", "أ"]
    assert {r["name"]: r["artwork_count"] for r in results} == {"أ": 1, "ب": 0}
    assert [r["name"] for r in api_client.get("/api/v1/artists?featured=true").json()["results"]] == [b.name]


def test_editor_creates_and_updates_artist(login_client, content_staff):
    client = login_client(content_staff)
    response = client.post(ADMIN, {"name": "لؤي كيالي", "biography": "رسام سوري", "contact_phone": "+963944567890"})
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["slug"] == "لؤي-كيالي" and body["contact_phone"] == "+963944567890"
    updated = client.patch(f"{ADMIN}/{body['id']}", {"status": "hidden", "is_featured": True}).json()
    assert updated["status"] == "hidden" and updated["is_featured"]
    assert AuditLog.objects.get(action="artist.updated").changes["status"] == {"from": "active", "to": "hidden"}


def test_photo_upload_replaces_old_photo(
    login_client, content_staff, artist_factory, image_file, django_capture_on_commit_callbacks
):
    artist = artist_factory()
    client = login_client(content_staff)
    with django_capture_on_commit_callbacks(execute=True):
        first = client.post(f"{ADMIN}/{artist.public_id}/photo", {"file": image_file()}, format="multipart")
    assert first.status_code == 200, first.json()
    with django_capture_on_commit_callbacks(execute=True):
        second = client.post(
            f"{ADMIN}/{artist.public_id}/photo", {"file": image_file("b.png", "PNG")}, format="multipart"
        )
    assert second.json()["photo"]["status"] == "pending"  # response is built before processing
    assert ImageAsset.objects.count() == 1
    public = client.get(f"/api/v1/artists/{artist.slug}").json()
    assert [v["width"] for v in public["photo"]["variants"]] == [400, 1000, 1200]


def test_invalid_photo_is_rejected(login_client, content_staff, artist_factory):
    from django.core.files.uploadedfile import SimpleUploadedFile

    artist = artist_factory()
    fake = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
    response = login_client(content_staff).post(f"{ADMIN}/{artist.public_id}/photo", {"file": fake}, format="multipart")
    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_IMAGE"
    assert not ImageAsset.objects.exists()


def test_artist_with_artworks_cannot_be_deleted(login_client, content_staff, artwork_factory, artist_factory):
    artwork = artwork_factory()
    client = login_client(content_staff)
    response = client.delete(f"{ADMIN}/{artwork.artist.public_id}")
    assert response.status_code == 409 and response.json()["error"]["code"] == "ARTIST_HAS_ARTWORKS"
    lonely = artist_factory()
    assert client.delete(f"{ADMIN}/{lonely.public_id}").status_code == 204


def test_customers_cannot_reach_admin_artists(login_client, customer):
    assert login_client(customer).get(ADMIN).status_code == 403

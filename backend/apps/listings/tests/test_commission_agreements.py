from decimal import Decimal

import pytest

from apps.artists.models import ArtistAgreement
from apps.audit.models import AuditLog
from apps.listings import services as listing_services

pytestmark = pytest.mark.django_db


def url(artist, suffix=""):
    return f"/api/v1/admin/artists/{artist.public_id}/agreements{suffix}"


def test_new_agreement_replaces_the_active_one(artist_factory, super_admin, login_client):
    artist = artist_factory()
    client = login_client(super_admin)
    empty = client.get(url(artist)).json()
    assert empty["active"] is None and empty["default_commission_rate"] == "15.00" and empty["can_manage"] is True
    assert client.post(url(artist), {"commission_rate": "12"}, format="json").status_code == 201
    body = client.post(url(artist), {"commission_rate": "10", "notes": "تجديد"}, format="json").json()
    assert body["active"]["commission_rate"] == "10.00" and body["active"]["notes"] == "تجديد"
    assert [h["commission_rate"] for h in body["history"]] == ["12.00"]
    assert body["history"][0]["status"] == "ended" and body["history"][0]["effective_to"]
    assert ArtistAgreement.objects.filter(artist=artist, status="active").count() == 1
    assert AuditLog.objects.filter(action="artist.agreement_created").count() == 2


def test_ending_returns_to_the_default_rate(
    artist_factory, artwork_factory, listing_factory, super_admin, login_client
):
    artist = artist_factory()
    listing = listing_factory(artwork_factory(published=True, artist=artist))
    client = login_client(super_admin)
    client.post(url(artist), {"commission_rate": "8"}, format="json")
    assert listing_services.commission_source(listing) == (Decimal("8.00"), "agreement")
    assert client.post(url(artist, "/end")).status_code == 200
    assert listing_services.commission_source(listing) == (Decimal("15.00"), "default")
    assert client.post(url(artist, "/end")).status_code == 409


def test_listing_rate_beats_the_agreement(artist_factory, artwork_factory, listing_factory, super_admin):
    from apps.artists import services

    artist = artist_factory()
    listing = listing_factory(artwork_factory(published=True, artist=artist))
    services.create_agreement(artist, actor=super_admin, commission_rate=Decimal("8"))
    listing.commission_rate_override = Decimal("20")
    assert listing_services.commission_source(listing) == (Decimal("20"), "listing")


def test_only_the_super_admin_sets_commissions(artist_factory, content_staff, make_user, login_client):
    artist = artist_factory()
    editor = login_client(content_staff)
    assert editor.get(url(artist)).json()["can_manage"] is False
    assert editor.post(url(artist), {"commission_rate": "5"}, format="json").status_code == 403
    ops = login_client(make_user(roles=["operations_staff"]))
    assert ops.get(url(artist)).status_code == 403
    sa = login_client(make_user(roles=["super_admin"]))
    assert sa.post(url(artist), {"commission_rate": "101"}, format="json").status_code == 400

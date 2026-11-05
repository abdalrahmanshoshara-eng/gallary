import pytest

from apps.artworks import services as artwork_services
from apps.favorites.models import Favorite

pytestmark = pytest.mark.django_db
URL = "/api/v1/favorites"


def test_add_list_ids_and_remove(login_client, customer, artwork_factory, listing_factory):
    client = login_client(customer)
    artwork = artwork_factory(published=True)
    listing_factory(artwork, price="250.00")
    assert client.put(f"{URL}/{artwork.public_id}").status_code == 201
    assert client.put(f"{URL}/{artwork.public_id}").status_code == 204  # idempotent
    assert Favorite.objects.count() == 1

    listed = client.get(URL).json()["results"]
    assert [a["slug"] for a in listed] == [artwork.slug] and listed[0]["offer"]["price_usd"] == "250.00"
    assert client.get(f"{URL}/ids").json() == {"ids": [str(artwork.public_id)]}

    assert client.delete(f"{URL}/{artwork.public_id}").status_code == 204
    assert client.get(URL).json()["results"] == []


def test_only_public_artworks_can_be_added(login_client, customer, artwork_factory):
    draft = artwork_factory()
    assert login_client(customer).put(f"{URL}/{draft.public_id}").status_code == 404


def test_hidden_artworks_disappear_from_the_list(login_client, customer, artwork_factory):
    client = login_client(customer)
    artwork = artwork_factory(published=True)
    client.put(f"{URL}/{artwork.public_id}")
    artwork_services.hide(artwork, actor=None)
    assert client.get(URL).json()["results"] == [] and client.get(f"{URL}/ids").json() == {"ids": []}
    artwork_services.publish(artwork, actor=None)
    assert len(client.get(URL).json()["results"]) == 1  # kept, shown again


def test_favorites_are_private(login_client, customer, make_user, artwork_factory, api_client):
    artwork = artwork_factory(published=True)
    login_client(customer).put(f"{URL}/{artwork.public_id}")
    assert login_client(make_user()).get(URL).json()["results"] == []
    assert api_client.get(URL).status_code == 403
    assert api_client.put(f"{URL}/{artwork.public_id}").status_code == 403


def test_favorites_are_for_customers(login_client, make_user, artwork_factory):
    artwork = artwork_factory(published=True)
    assert login_client(make_user(roles=["content_staff"])).put(f"{URL}/{artwork.public_id}").status_code == 403

import pytest

from apps.audit.models import AuditLog
from apps.catalog.models import Category, Material, Technique

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/catalog"


def test_seed_matches_requirements():
    assert set(Category.objects.values_list("name", flat=True)) == {
        "لوحات",
        "منحوتات",
        "أعمال يدوية",
        "فن زخرفي",
        "أعمال مختلطة",
        "تصنيفات أخرى",
    }
    assert Material.objects.count() == 12 and Technique.objects.count() == 10
    assert Technique.objects.filter(name="شمعي / Encaustic").exists()


def test_public_category_tree_lists_active_only(api_client, category):
    Category.objects.create(name="بورتريه", slug="portrait", parent=category)
    Category.objects.create(name="قديم", slug="old", parent=category, is_active=False)
    Category.objects.filter(slug="other-categories").update(is_active=False)
    tree = api_client.get("/api/v1/catalog/categories").json()
    names = [c["name"] for c in tree]
    assert "تصنيفات أخرى" not in names
    paintings = next(c for c in tree if c["slug"] == "paintings")
    assert paintings["children"] == [{"name": "بورتريه", "slug": "portrait"}]


@pytest.mark.parametrize("roles", [None, [], ["operations_staff"], ["auction_manager"]])
def test_only_content_staff_and_super_admin_manage_terms(roles, make_user, login_client, api_client):
    client = api_client if roles is None else login_client(make_user(roles=roles))
    assert client.post(f"{ADMIN}/materials", {"name": "زجاج"}).status_code == 403
    assert client.get(f"{ADMIN}/materials").status_code == 403


@pytest.mark.parametrize("roles", [["content_staff"], ["super_admin"]])
def test_editors_create_terms_with_arabic_slugs(roles, make_user, login_client):
    client = login_client(make_user(roles=roles))
    response = client.post(f"{ADMIN}/materials", {"name": "زجاج معشّق"})
    assert response.status_code == 201, response.json()
    assert response.json()["slug"] == "زجاج-معشق"  # tashkeel removed, Arabic kept
    assert AuditLog.objects.filter(action="material.created").exists()


def test_categories_are_two_levels(login_client, content_staff, category):
    client = login_client(content_staff)
    sub = client.post(f"{ADMIN}/categories", {"name": "مناظر", "parent": category.pk}).json()
    response = client.post(f"{ADMIN}/categories", {"name": "بحرية", "parent": sub["id"]})
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_PARENT"
    response = client.patch(f"{ADMIN}/categories/{category.pk}", {"parent": category.pk})
    assert response.status_code == 409


def test_terms_in_use_are_deactivated_not_deleted(login_client, content_staff, artwork_factory):
    artwork = artwork_factory()
    material = Material.objects.get(slug="wood")
    artwork.materials.add(material)
    client = login_client(content_staff)
    listed = {m["slug"]: m for m in client.get(f"{ADMIN}/materials").json()}
    assert listed["wood"]["usage_count"] == 1
    response = client.delete(f"{ADMIN}/materials/{material.pk}")
    assert response.status_code == 409 and response.json()["error"]["code"] == "TERM_IN_USE"
    assert client.patch(f"{ADMIN}/materials/{material.pk}", {"is_active": False}).json()["is_active"] is False
    assert client.delete(f"{ADMIN}/materials/{Material.objects.get(slug='iron').pk}").status_code == 204


def test_duplicate_slug_is_rejected(login_client, content_staff):
    client = login_client(content_staff)
    response = client.post(f"{ADMIN}/techniques", {"name": "زيت آخر", "slug": "oil"})
    assert response.status_code == 400 and "slug" in response.json()["error"]["details"]


def test_public_terms(api_client):
    Material.objects.filter(slug="resin").update(is_active=False)
    slugs = [m["slug"] for m in api_client.get("/api/v1/catalog/materials").json()]
    assert "resin" not in slugs and "wood" in slugs
    assert len(api_client.get("/api/v1/catalog/techniques").json()) == 10

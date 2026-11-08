from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.cms.models import Banner, FaqItem, Page, PageVersion
from apps.orders import policy

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/content"


# --- pages and versions (F-CMS-01) ------------------------------------------------------------------
def test_seeded_pages_keep_the_accepted_policy_version(api_client):
    assert policy.current_version() == "2026-11-05"
    links = {p["slug"] for p in api_client.get("/api/v1/pages").json()}
    assert links == {"deposit-policy", "about"}  # terms and privacy are drafts until reviewed
    assert api_client.get("/api/v1/pages/terms").status_code == 404
    page = api_client.get("/api/v1/pages/deposit-policy").json()
    assert page["code"] == "2026-11-05" and page["body"].startswith("- تأكيد الطلب")


def test_publishing_creates_an_immutable_version_and_moves_checkout_to_it(super_admin, login_client, api_client):
    client = login_client(super_admin)
    detail = client.get(f"{ADMIN}/pages/deposit-policy").json()
    assert detail["unpublished_changes"] is True and detail["can_edit"] is True  # seeded auction draft
    saved = client.put(
        f"{ADMIN}/pages/deposit-policy", {"title": "سياسة العربون", "body": "- نص جديد"}, format="json"
    ).json()
    assert saved["draft_body"] == "- نص جديد" and saved["published"]["code"] == "2026-11-05"
    assert api_client.get("/api/v1/pages/deposit-policy").json()["code"] == "2026-11-05"  # drafts are private
    published = client.post(f"{ADMIN}/pages/deposit-policy/publish").json()
    today = timezone.localdate().isoformat()
    assert published["published"]["number"] == 2 and published["published"]["code"] == today
    assert published["unpublished_changes"] is False and [v["number"] for v in published["versions"]] == [2, 1]
    assert client.post(f"{ADMIN}/pages/deposit-policy/publish").status_code == 409  # nothing new
    assert policy.current_version() == today
    assert api_client.get("/api/v1/orders/policy").status_code in (401, 403)  # customers only
    old = client.get(f"{ADMIN}/pages/deposit-policy/versions/1").json()
    assert old["code"] == "2026-11-05"
    with pytest.raises(RuntimeError):
        PageVersion.objects.get(number=1, page__slug="deposit-policy").save()
    assert AuditLog.objects.filter(action="page.published", entity_id="deposit-policy").exists()


def test_same_day_versions_get_distinct_codes(super_admin, login_client):
    client = login_client(super_admin)
    codes = []
    for body in ("أ", "ب"):
        client.put(f"{ADMIN}/pages/about", {"title": "من نحن", "body": body}, format="json")
        codes.append(client.post(f"{ADMIN}/pages/about/publish").json()["published"]["code"])
    today = timezone.localdate().isoformat()
    assert codes == [today + "-2", today + "-3"] or codes == [today, today + "-2"]


def test_checkout_policy_endpoint_serves_the_published_text(customer, login_client, super_admin):
    admin = login_client(super_admin)
    admin.put(f"{ADMIN}/pages/deposit-policy", {"title": "السياسة", "body": "- البند الوحيد"}, format="json")
    admin.post(f"{ADMIN}/pages/deposit-policy/publish")
    body = login_client(customer).get("/api/v1/orders/policy").json()
    assert body["title"] == "السياسة" and body["body"] == "- البند الوحيد" and body["reservation_hours"] == 24


def test_only_the_super_admin_edits_the_deposit_policy(content_staff, login_client, make_user):
    editor = login_client(content_staff)
    detail = editor.get(f"{ADMIN}/pages/deposit-policy").json()
    assert detail["can_edit"] is False
    assert editor.put(f"{ADMIN}/pages/deposit-policy", {"title": "x", "body": "y"}, format="json").status_code == 403
    assert editor.post(f"{ADMIN}/pages/deposit-policy/publish").status_code == 403
    assert editor.put(f"{ADMIN}/pages/terms", {"title": "الشروط", "body": "## بند"}, format="json").status_code == 200
    assert editor.post(f"{ADMIN}/pages/terms/publish").status_code == 200
    assert editor.get(f"{ADMIN}/pages/nope").status_code == 404
    assert login_client(make_user(roles=["operations_staff"])).get(f"{ADMIN}/pages").status_code == 403


def test_empty_drafts_cannot_be_published(content_staff, login_client):
    client = login_client(content_staff)
    client.put(f"{ADMIN}/pages/privacy", {"title": "", "body": "x"}, format="json")
    response = client.post(f"{ADMIN}/pages/privacy/publish")
    assert response.status_code == 400 and "title" in response.json()["error"]["details"]


# --- FAQ (F-CMS-02) ------------------------------------------------------------------------------------
def test_faq_crud_order_and_visibility(content_staff, login_client, api_client):
    client = login_client(content_staff)
    assert client.post(f"{ADMIN}/faq", {"question": "", "answer": "x"}, format="json").status_code == 400
    client.post(f"{ADMIN}/faq", {"question": "كيف أدفع؟", "answer": "عبر WhatsApp."}, format="json")
    rows = client.post(f"{ADMIN}/faq", {"question": "هل التوصيل متاح؟", "answer": "نعم."}, format="json").json()
    second = rows[1]["id"]
    rows = client.post(f"{ADMIN}/faq/{second}/move", {"direction": "up"}, format="json").json()
    assert [r["question"] for r in rows] == ["هل التوصيل متاح؟", "كيف أدفع؟"]
    client.patch(f"{ADMIN}/faq/{second}", {"is_active": False}, format="json")
    assert [r["question"] for r in api_client.get("/api/v1/faq").json()] == ["كيف أدفع؟"]
    client.delete(f"{ADMIN}/faq/{second}")
    assert FaqItem.objects.count() == 1


# --- banners and featured (F-CMS-03/04) --------------------------------------------------------------
def test_banners_need_an_image_and_a_safe_link(
    content_staff, login_client, image_file, api_client, django_capture_on_commit_callbacks
):
    client = login_client(content_staff)
    assert client.post(f"{ADMIN}/banners", {"title": "معرض الربيع"}, format="multipart").status_code == 400
    bad = client.post(
        f"{ADMIN}/banners",
        {"title": "x", "link_url": "javascript:alert(1)", "link_label": "اذهب", "image": image_file()},
        format="multipart",
    )
    assert bad.status_code == 400 and "link_url" in bad.json()["error"]["details"]
    with django_capture_on_commit_callbacks(execute=True):
        rows = client.post(
            f"{ADMIN}/banners",
            {
                "title": "معرض الربيع",
                "subtitle": "أعمال جديدة",
                "link_url": "/auctions",
                "link_label": "المزادات",
                "image": image_file(),
            },
            format="multipart",
        ).json()
    assert rows[0]["state"] == "live" and rows[0]["image"]["status"] == "pending"  # processed after commit
    assert client.get(f"{ADMIN}/banners").json()[0]["image"]["status"] == "ready"
    home = api_client.get("/api/v1/home").json()
    assert [b["title"] for b in home["banners"]] == ["معرض الربيع"] and home["banners"][0]["image"]["variants"]
    later = (timezone.now() + timedelta(days=2)).isoformat()
    rows = client.patch(f"{ADMIN}/banners/{rows[0]['id']}", {"starts_at": later}, format="multipart").json()
    assert rows[0]["state"] == "scheduled" and api_client.get("/api/v1/home").json()["banners"] == []
    client.delete(f"{ADMIN}/banners/{rows[0]['id']}")
    assert not Banner.objects.exists()


def test_featured_artworks_curated_in_order(content_staff, login_client, artwork_factory, listing_factory, api_client):
    from apps.artworks import services as artwork_services

    a, b = artwork_factory(published=True, title="الأول"), artwork_factory(published=True, title="الثاني")
    listing_factory(b, price="300.00")
    draft = artwork_factory(title="مسودة")
    client = login_client(content_staff)
    assert client.post(f"{ADMIN}/featured", {"artwork": str(draft.public_id)}, format="json").status_code == 400
    client.post(f"{ADMIN}/featured", {"artwork": str(a.public_id)}, format="json")
    client.post(f"{ADMIN}/featured", {"artwork": str(b.public_id)}, format="json")
    assert client.post(f"{ADMIN}/featured", {"artwork": str(b.public_id)}, format="json").status_code == 409
    client.post(f"{ADMIN}/featured/{b.public_id}/move", {"direction": "up"}, format="json")
    home = api_client.get("/api/v1/home").json()["featured"]
    assert [x["title"] for x in home] == ["الثاني", "الأول"] and home[0]["offer"]["price_usd"] == "300.00"
    artwork_services.hide(a, actor=None)
    assert [x["title"] for x in api_client.get("/api/v1/home").json()["featured"]] == ["الثاني"]
    admin_rows = client.get(f"{ADMIN}/featured").json()
    assert {r["title"]: r["is_public"] for r in admin_rows} == {"الثاني": True, "الأول": False}
    client.delete(f"{ADMIN}/featured/{a.public_id}")
    assert len(client.get(f"{ADMIN}/featured").json()) == 1


def test_pages_exist_even_on_a_fresh_database():
    Page.objects.all().update(published=None)
    PageVersion.objects.all().delete()
    assert policy.current_version() == policy.DEFAULT_CODE

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.artworks.models import PublicationStatus
from apps.auctions.models import AuctionRequest, RequestStatus

pytestmark = pytest.mark.django_db
MINE = "/api/v1/auction-requests"
ADMIN = "/api/v1/admin/auction-requests"
FORM = {
    "work_title": "بوابة دمشق القديمة",
    "work_description": "لوحة زيتية على قماش",
    "artist_name": "سامي الحلبي",
    "dimensions_text": "60×80 سم",
    "year_text": "1998",
    "expected_price": "1500",
}


@pytest.fixture
def submitted(login_client, customer, image_file, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = login_client(customer).post(
            MINE, {**FORM, "images": [image_file(), image_file("b.jpg")]}, format="multipart"
        )
    assert response.status_code == 201, response.json()
    return response.json()


def move(client, rid, to, message=""):
    return client.post(f"{ADMIN}/{rid}/transition", {"to": to, "message": message}, format="json")


def test_customer_submits_with_images_and_follows_it(submitted, login_client, customer):
    assert submitted["status"] == "submitted" and len(submitted["images"]) == 2
    assert submitted["can_edit"] is False and submitted["can_withdraw"] is True
    assert [h["status"] for h in submitted["history"]] == ["submitted"]
    listed = login_client(customer).get(MINE).json()
    assert [r["id"] for r in listed] == [submitted["id"]]


def test_requests_are_private_to_their_owner(submitted, login_client, make_user):
    other = login_client(make_user())
    assert other.get(f"{MINE}/{submitted['id']}").status_code == 404
    assert other.post(f"{MINE}/{submitted['id']}/withdraw").status_code == 404
    assert login_client(make_user(roles=["operations_staff"])).get(ADMIN).status_code == 403


def test_more_info_round_trip_with_customer_message(submitted, login_client, customer, manager):
    staff = login_client(manager)
    rid = submitted["id"]
    assert move(staff, rid, "under_review").status_code == 200
    assert move(staff, rid, "needs_more_info").status_code == 400  # a message is required
    asked = move(staff, rid, "needs_more_info", "أرسل صورة للتوقيع من فضلك")
    assert asked.status_code == 200 and "needs_more_info" in [h["status"] for h in asked.json()["history"]]

    mine = login_client(customer)
    detail = mine.get(f"{MINE}/{rid}").json()
    assert detail["can_edit"] is True and detail["messages"][0]["body"] == "أرسل صورة للتوقيع من فضلك"
    updated = mine.patch(f"{MINE}/{rid}", {"year_text": "1997"}, format="multipart")
    assert updated.status_code == 200 and updated.json()["status"] == "under_review"
    assert updated.json()["year_text"] == "1997"
    assert mine.patch(f"{MINE}/{rid}", {"year_text": "1990"}, format="multipart").status_code == 409


def test_internal_notes_never_reach_the_customer(submitted, login_client, customer, manager):
    staff = login_client(manager)
    staff.post(f"{ADMIN}/{submitted['id']}/notes", {"body": "سعر مبالغ فيه", "visibility": "internal"}, format="json")
    assert login_client(customer).get(f"{MINE}/{submitted['id']}").json()["messages"] == []
    notes = staff.get(f"{ADMIN}/{submitted['id']}").json()["notes"]
    assert notes[0]["body"] == "سعر مبالغ فيه" and notes[0]["author"] == manager.display_name


def test_approval_requires_agreed_commission_then_builds_artwork_and_auction(
    submitted, login_client, customer, manager, category, django_capture_on_commit_callbacks
):
    staff = login_client(manager)
    rid = submitted["id"]
    move(staff, rid, "under_review")
    negotiation = move(staff, rid, "negotiation").json()
    assert "approved" not in negotiation["actions"] and "set_commission" in negotiation["actions"]
    assert move(staff, rid, "approved").status_code == 409
    agreed = staff.post(f"{ADMIN}/{rid}/commission", {"rate": "12.50"}, format="json").json()
    assert agreed["agreed_commission_rate"] == "12.50" and "approved" in agreed["actions"]
    approved = move(staff, rid, "approved", "تمت الموافقة")
    assert approved.status_code == 200 and approved.json()["actions"] == ["create_artwork"]

    with django_capture_on_commit_callbacks(execute=True):
        built = staff.post(f"{ADMIN}/{rid}/artwork", {"category": category.slug}, format="json")
    assert built.status_code == 201, built.json()
    assert built.json()["actions"] == ["create_auction"]
    req = AuctionRequest.objects.get(public_id=rid)
    artwork = req.resulting_artwork
    assert artwork.owner_user == customer and artwork.creator_name_override == "سامي الحلبي"
    assert artwork.year_created == 1998 and artwork.images.count() == 2
    assert artwork.publication_status == PublicationStatus.DRAFT

    now = timezone.now()
    created = staff.post(
        "/api/v1/admin/auctions",
        {
            "artwork": str(artwork.public_id),
            "request": rid,
            "commission_rate": "40",  # ignored: the agreed share applies (BR-606)
            "starting_price": "1000",
            "minimum_increment": "50",
            "starts_at": (now + timedelta(hours=2)).isoformat(),
            "ends_at": (now + timedelta(days=2)).isoformat(),
        },
        format="json",
    )
    assert created.status_code == 201, created.json()
    assert created.json()["commission_rate"] == "12.50"
    # Scheduling publishes the request's artwork: the auction manager owns the flow.
    scheduled = staff.post(f"/api/v1/admin/auctions/{created.json()['id']}/schedule")
    assert scheduled.status_code == 200, scheduled.json()
    artwork.refresh_from_db()
    assert artwork.publication_status == PublicationStatus.PUBLISHED
    mine = login_client(customer).get(f"{MINE}/{rid}").json()
    assert mine["status"] == "approved" and mine["auction_id"] == created.json()["id"]
    assert mine["can_withdraw"] is False


def test_withdraw_before_decision_only(submitted, login_client, customer, manager):
    mine = login_client(customer)
    withdrawn = mine.post(f"{MINE}/{submitted['id']}/withdraw")
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "withdrawn"
    assert mine.post(f"{MINE}/{submitted['id']}/withdraw").status_code == 409
    assert move(login_client(manager), submitted["id"], "under_review").status_code == 409
    assert AuctionRequest.objects.get().status == RequestStatus.WITHDRAWN


def test_image_limit(login_client, customer, image_file):
    images = [image_file(f"{i}.jpg", size=(200, 200)) for i in range(11)]
    response = login_client(customer).post(MINE, {**FORM, "images": images}, format="multipart")
    assert response.status_code == 400


def test_staff_cannot_submit_requests(login_client, manager):
    assert login_client(manager).post(MINE, FORM, format="multipart").status_code == 403

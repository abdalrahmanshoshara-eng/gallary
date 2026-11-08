"""
Auction requests (BR-601…607): a customer offers a work; staff review, agree the platform's
share with the owner, then create the artwork and auction themselves (a request never
creates an auction automatically).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.artworks import services as artwork_services
from apps.artworks.models import ArtworkImage
from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.media import services as media
from apps.media.models import ImagePurpose
from apps.notifications import services as notifications

from .models import (
    FINAL_REQUEST_STATUSES,
    AuctionRequest,
    AuctionRequestImage,
    AuctionRequestNote,
    NoteVisibility,
    RequestStatus,
    RequestStatusHistory,
)

MAX_IMAGES = 10  # BR-604
CUSTOMER_FIELDS = (
    "work_title",
    "work_description",
    "artist_name",
    "artist_info",
    "category_hint",
    "dimensions_text",
    "year_text",
    "expected_price",
    "customer_notes",
)

# Staff transitions (BR-602). Approval has its own function (commission rule).
STAFF_TRANSITIONS = {
    RequestStatus.SUBMITTED: {RequestStatus.UNDER_REVIEW, RequestStatus.REJECTED},
    RequestStatus.UNDER_REVIEW: {RequestStatus.NEEDS_MORE_INFO, RequestStatus.NEGOTIATION, RequestStatus.REJECTED},
    RequestStatus.NEEDS_MORE_INFO: {RequestStatus.UNDER_REVIEW, RequestStatus.REJECTED},
    RequestStatus.NEGOTIATION: {RequestStatus.UNDER_REVIEW, RequestStatus.REJECTED},
}


class RequestStateError(ConflictError):
    code = "INVALID_REQUEST_STATE"
    message = "لا يمكن تنفيذ هذه العملية في حالة الطلب الحالية."


REQUEST_NOTICES = {
    RequestStatus.UNDER_REVIEW: "request.under_review",
    RequestStatus.NEEDS_MORE_INFO: "request.needs_more_info",
    RequestStatus.NEGOTIATION: "request.negotiation",
    RequestStatus.APPROVED: "request.approved",
    RequestStatus.REJECTED: "request.rejected",
}


def _request_link(req: AuctionRequest) -> str:
    return f"/auction-requests/{req.public_id}"


def _move(req: AuctionRequest, to: str, actor, *, message: str = "") -> None:
    before = req.status
    req.status = to
    req.save(update_fields=["status", "updated_at"])
    RequestStatusHistory.objects.create(request=req, from_status=before, to_status=to, actor=actor)
    audit.record(actor=actor, action=f"auction_request.{to}", entity=req, changes={"from": before, "to": to})
    kind = REQUEST_NOTICES.get(to)
    if kind and (actor is None or actor.pk != req.user_id):  # not for the customer's own moves
        notifications.notify(
            req.user_id,
            kind,
            params={"title": req.work_title, "message": message.strip()},
            link=_request_link(req),
        )


def _add_images(req: AuctionRequest, files, actor) -> None:
    existing = req.images.count()
    if existing + len(files) > MAX_IMAGES:
        raise ConflictError(f"الحد الأقصى {MAX_IMAGES} صور.", code="TOO_MANY_IMAGES", http_status=400)
    for index, upload in enumerate(files):
        asset = media.ingest_image(upload, purpose=ImagePurpose.AUCTION_REQUEST, user=actor)
        AuctionRequestImage.objects.create(request=req, asset=asset, sort_order=existing + index)


@transaction.atomic
def submit(*, user, data: dict, files=()) -> AuctionRequest:
    req = AuctionRequest.objects.create(
        user=user, contact_phone=user.phone, **{k: data[k] for k in CUSTOMER_FIELDS if k in data}
    )
    _add_images(req, list(files), user)
    RequestStatusHistory.objects.create(request=req, to_status=req.status, actor=user)
    audit.record(actor=user, action="auction_request.submitted", entity=req)
    return req


@transaction.atomic
def customer_update(req: AuctionRequest, *, user, data: dict, files=()) -> AuctionRequest:
    """BR-603: the customer edits only when asked for more information; it then returns to review."""
    req = AuctionRequest.objects.select_for_update().get(pk=req.pk)
    if req.user_id != user.pk:
        raise ConflictError(code="NOT_FOUND", http_status=404)
    if req.status != RequestStatus.NEEDS_MORE_INFO:
        raise RequestStateError("يمكن تعديل الطلب فقط عندما تطلب الإدارة معلومات إضافية.")
    for field in CUSTOMER_FIELDS:
        if field in data:
            setattr(req, field, data[field])
    req.save()
    _add_images(req, list(files), user)
    _move(req, RequestStatus.UNDER_REVIEW, user)
    return req


@transaction.atomic
def withdraw(req: AuctionRequest, *, user) -> AuctionRequest:
    req = AuctionRequest.objects.select_for_update().get(pk=req.pk)
    if req.user_id != user.pk or req.status in FINAL_REQUEST_STATUSES:
        raise RequestStateError("لا يمكن سحب الطلب بعد صدور القرار.")
    _move(req, RequestStatus.WITHDRAWN, user)
    return req


@transaction.atomic
def staff_transition(req: AuctionRequest, *, actor, to: str, message: str = "") -> AuctionRequest:
    req = AuctionRequest.objects.select_for_update().get(pk=req.pk)
    if to not in STAFF_TRANSITIONS.get(req.status, set()):
        raise RequestStateError()
    if to == RequestStatus.NEEDS_MORE_INFO and not message.strip():
        raise ConflictError(
            "اكتب للعميل ما المطلوب منه.", code="VALIDATION_ERROR", http_status=400, details={"message": ["مطلوب."]}
        )
    if message.strip():
        AuctionRequestNote.objects.create(
            request=req, author=actor, visibility=NoteVisibility.CUSTOMER, body=message.strip()
        )
    _move(req, to, actor, message=message)
    return req


@transaction.atomic
def add_note(req: AuctionRequest, *, actor, body: str, visibility: str) -> AuctionRequestNote:
    if not body.strip():
        raise ConflictError(
            "نص الملاحظة مطلوب.", code="VALIDATION_ERROR", http_status=400, details={"body": ["مطلوب."]}
        )
    note = AuctionRequestNote.objects.create(request=req, author=actor, visibility=visibility, body=body.strip())
    if visibility == NoteVisibility.CUSTOMER and actor.pk != req.user_id:
        notifications.notify(
            req.user_id,
            "request.message",
            params={"title": req.work_title, "message": note.body},
            link=_request_link(req),
        )
    return note


@transaction.atomic
def set_commission(req: AuctionRequest, *, actor, rate: Decimal, note: str = "") -> AuctionRequest:
    """BR-606: the share agreed with the owner during negotiation (zero allowed)."""
    req = AuctionRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != RequestStatus.NEGOTIATION:
        raise RequestStateError("تُسجَّل النسبة المتفق عليها في مرحلة التفاوض.")
    if not (Decimal(0) <= rate <= Decimal(100)):
        raise ConflictError("النسبة بين 0 و100.", code="VALIDATION_ERROR", http_status=400, details={"rate": ["0–100"]})
    req.agreed_commission_rate = rate
    req.commission_agreed_at = timezone.now()
    req.commission_agreed_by = actor
    req.save()
    if note.strip():
        AuctionRequestNote.objects.create(
            request=req, author=actor, visibility=NoteVisibility.INTERNAL, body=note.strip()
        )
    audit.record(actor=actor, action="auction_request.commission_agreed", entity=req, changes={"rate": str(rate)})
    return req


@transaction.atomic
def approve(req: AuctionRequest, *, actor, message: str = "") -> AuctionRequest:
    req = AuctionRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != RequestStatus.NEGOTIATION:
        raise RequestStateError("الموافقة تتم بعد التفاوض.")
    if req.agreed_commission_rate is None:
        raise ConflictError("سجّل نسبة المنصة المتفق عليها أولاً (BR-606).", code="COMMISSION_REQUIRED")
    if message.strip():
        AuctionRequestNote.objects.create(
            request=req, author=actor, visibility=NoteVisibility.CUSTOMER, body=message.strip()
        )
    _move(req, RequestStatus.APPROVED, actor, message=message)
    return req


@transaction.atomic
def link_auction(req: AuctionRequest, *, auction) -> None:
    req.resulting_auction = auction
    req.save(update_fields=["resulting_auction", "updated_at"])


@transaction.atomic
def create_artwork(req: AuctionRequest, *, actor, category):
    """BR-607: staff turn an approved request into a draft artwork owned by the requester,
    pre-filled from the request (photos copied); they complete and publish it in the editor."""
    req = AuctionRequest.objects.select_for_update().select_related("user").get(pk=req.pk)
    if req.status != RequestStatus.APPROVED:
        raise RequestStateError("يُنشأ العمل من طلب موافق عليه فقط.")
    if req.resulting_artwork_id:
        raise RequestStateError("أُنشئ عمل من هذا الطلب بالفعل.")
    year = int(req.year_text) if req.year_text.strip().isdigit() and 1000 <= int(req.year_text) <= 2100 else None
    artwork = artwork_services.create_artwork(
        actor=actor,
        data={
            "title": req.work_title,
            "description": req.work_description,
            "category": category,
            "creator_name_override": req.artist_name,
            "owner_user": req.user,
            "owner_name": req.user.display_name or req.user.phone,
            "year_created": year,
            "internal_notes": f"من طلب المزاد {req.public_id}",
        },
    )
    for index, image in enumerate(req.images.select_related("asset").order_by("sort_order")):
        asset = media.copy_image(image.asset, purpose=ImagePurpose.ARTWORK, user=actor)
        ArtworkImage.objects.create(
            artwork=artwork, asset=asset, alt_text=artwork.title, sort_order=index + 1, is_primary=index == 0
        )
    req.resulting_artwork = artwork
    req.save(update_fields=["resulting_artwork", "updated_at"])
    audit.record(
        actor=actor, action="auction_request.artwork_created", entity=req, changes={"artwork": str(artwork.public_id)}
    )
    return artwork

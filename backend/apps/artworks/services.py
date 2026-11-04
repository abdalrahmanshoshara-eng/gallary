"""Artwork lifecycle: drafting, images, publication and archive (BR-101…105, BR-802)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.artists.models import ArtistStatus
from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.core.slugs import unique_slug
from apps.media import services as media
from apps.media.models import ImagePurpose, ImageStatus

from .models import ArchiveVisibility, Artwork, ArtworkImage, PublicationStatus

M2M_FIELDS = ("materials", "techniques", "tags")
AUDITED = ("title", "slug", "category", "artist", "creator_name_override", "executor", "owner_name")
MAX_IMAGES = 20


class PublishRequirementsError(ConflictError):
    code = "PUBLISH_REQUIREMENTS"
    message = "لا يمكن نشر العمل قبل استكمال متطلبات النشر."


class InvalidTransitionError(ConflictError):
    code = "INVALID_STATUS_TRANSITION"
    message = "لا يمكن تنفيذ هذا الإجراء في حالة العمل الحالية."


class ArtworkDeleteError(ConflictError):
    code = "ARTWORK_NOT_DELETABLE"
    message = "لا يمكن حذف عمل سبق نشره. يمكنك إخفاؤه أو أرشفته."


class LastImageError(ConflictError):
    code = "LAST_IMAGE"
    message = "لا يمكن حذف آخر صورة لعمل منشور."


class TooManyImagesError(ConflictError):
    code = "TOO_MANY_IMAGES"
    message = f"الحد الأقصى {MAX_IMAGES} صورة للعمل الواحد."


def _lock(artwork: Artwork) -> Artwork:
    return Artwork.objects.select_for_update().get(pk=artwork.pk)


# --- create / update ------------------------------------------------------------------------
@transaction.atomic
def create_artwork(*, actor, data: dict) -> Artwork:
    m2m = {f: data.pop(f, None) for f in M2M_FIELDS}
    slug = data.pop("slug", "") or unique_slug(Artwork, data["title"])
    artwork = Artwork.objects.create(slug=slug, created_by=actor, **data)
    for field, values in m2m.items():
        if values:
            getattr(artwork, field).set(values)
    audit.record(actor=actor, action="artwork.created", entity=artwork, changes={"title": artwork.title})
    return artwork


@transaction.atomic
def update_artwork(artwork: Artwork, *, actor, data: dict) -> Artwork:
    artwork = _lock(artwork)
    m2m = {f: data.pop(f) for f in M2M_FIELDS if f in data}
    changes = {}
    for field, value in data.items():
        old = getattr(artwork, field)
        if old != value:
            if field in AUDITED:
                changes[field] = {
                    "from": str(old) if old is not None else None,
                    "to": str(value) if value is not None else None,
                }
            setattr(artwork, field, value)
    if not artwork.artist_id and not artwork.creator_name_override:
        raise ConflictError("يجب تحديد الفنان أو اسم المُبدع.", code="CREATOR_REQUIRED")
    artwork.save()
    for field, values in m2m.items():
        getattr(artwork, field).set(values)
    if changes:
        audit.record(actor=actor, action="artwork.updated", entity=artwork, changes=changes)
    return artwork


# --- publication (BR-102, BR-103) -----------------------------------------------------------
def publish_problems(artwork: Artwork) -> list[str]:
    problems = []
    primary = artwork.images.filter(is_primary=True).select_related("asset").first()
    if primary is None:
        problems.append("primary_image_missing")
    elif primary.asset.status != ImageStatus.READY:
        problems.append("primary_image_not_ready")
    if not artwork.category.is_active:
        problems.append("category_inactive")
    if artwork.artist_id and artwork.artist.status != ArtistStatus.ACTIVE:
        problems.append("artist_hidden")
    if not artwork.artist_id and not artwork.creator_name_override:
        problems.append("creator_missing")
    if not artwork.title.strip():
        problems.append("title_missing")
    return problems


@transaction.atomic
def publish(artwork: Artwork, *, actor) -> Artwork:
    artwork = _lock(artwork)
    if artwork.publication_status == PublicationStatus.PUBLISHED:
        raise InvalidTransitionError()
    problems = publish_problems(artwork)
    if problems:
        raise PublishRequirementsError(details={"problems": problems})
    previous = artwork.publication_status
    artwork.publication_status = PublicationStatus.PUBLISHED
    artwork.published_at = artwork.published_at or timezone.now()
    artwork.save(update_fields=["publication_status", "published_at", "updated_at"])
    audit.record(actor=actor, action="artwork.published", entity=artwork, changes={"from": previous})
    return artwork


@transaction.atomic
def hide(artwork: Artwork, *, actor, reason: str = "") -> Artwork:
    artwork = _lock(artwork)
    if artwork.publication_status != PublicationStatus.PUBLISHED:
        raise InvalidTransitionError()
    artwork.publication_status = PublicationStatus.HIDDEN
    artwork.save(update_fields=["publication_status", "updated_at"])
    audit.record(actor=actor, action="artwork.hidden", entity=artwork, reason=reason)
    return artwork


# --- archive (BR-105, BR-802) ---------------------------------------------------------------
@transaction.atomic
def archive(artwork: Artwork, *, actor, visibility: str = ArchiveVisibility.VISIBLE, reason: str = "") -> Artwork:
    artwork = _lock(artwork)
    if artwork.published_at is None:
        raise InvalidTransitionError("لا يمكن أرشفة عمل لم يُنشر من قبل.")
    artwork.archived_at = artwork.archived_at or timezone.now()
    artwork.archive_visibility = visibility
    artwork.save(update_fields=["archived_at", "archive_visibility", "updated_at"])
    audit.record(
        actor=actor, action="artwork.archived", entity=artwork, changes={"visibility": visibility}, reason=reason
    )
    return artwork


@transaction.atomic
def unarchive(artwork: Artwork, *, actor) -> Artwork:
    artwork = _lock(artwork)
    if artwork.archived_at is None:
        raise InvalidTransitionError()
    artwork.archived_at = None
    artwork.save(update_fields=["archived_at", "updated_at"])
    audit.record(actor=actor, action="artwork.unarchived", entity=artwork)
    return artwork


@transaction.atomic
def delete_artwork(artwork: Artwork, *, actor) -> None:
    artwork = _lock(artwork)
    if artwork.published_at is not None:
        raise ArtworkDeleteError()
    images = list(artwork.images.select_related("asset"))
    audit.record(actor=actor, action="artwork.deleted", entity=artwork, changes={"title": artwork.title})
    artwork.delete()  # cascades ArtworkImage rows; assets are removed below
    for image in images:
        media.delete_asset(image.asset)


# --- images -------------------------------------------------------------------------------------
@transaction.atomic
def add_image(artwork: Artwork, upload, *, actor, alt_text: str = "") -> ArtworkImage:
    artwork = _lock(artwork)
    count = artwork.images.count()
    if count >= MAX_IMAGES:
        raise TooManyImagesError()
    asset = media.ingest_image(upload, purpose=ImagePurpose.ARTWORK, user=actor)
    next_order = (artwork.images.aggregate(m=Max("sort_order"))["m"] or 0) + 1
    return ArtworkImage.objects.create(
        artwork=artwork, asset=asset, alt_text=alt_text or artwork.title, sort_order=next_order, is_primary=count == 0
    )


@transaction.atomic
def reorder_images(artwork: Artwork, ordered_ids: list, *, actor) -> None:
    artwork = _lock(artwork)
    images = {str(i.public_id): i for i in artwork.images.all()}
    if set(map(str, ordered_ids)) != set(images) or len(ordered_ids) != len(images):
        raise ConflictError("يجب أن تتضمن القائمة كل صور العمل مرة واحدة.", code="INVALID_IMAGE_ORDER")
    for position, image_id in enumerate(ordered_ids, start=1):
        image = images[str(image_id)]
        if image.sort_order != position:
            image.sort_order = position
            image.save(update_fields=["sort_order"])


@transaction.atomic
def update_image(
    image: ArtworkImage, *, actor, alt_text: str | None = None, make_primary: bool = False
) -> ArtworkImage:
    artwork = _lock(image.artwork)
    if alt_text is not None:
        image.alt_text = alt_text
        image.save(update_fields=["alt_text"])
    if make_primary and not image.is_primary:
        if artwork.publication_status == PublicationStatus.PUBLISHED and image.asset.status != ImageStatus.READY:
            raise ConflictError("لا يمكن جعل صورة قيد المعالجة صورةً رئيسية لعمل منشور.", code="IMAGE_NOT_READY")
        artwork.images.filter(is_primary=True).update(is_primary=False)
        image.is_primary = True
        image.save(update_fields=["is_primary"])
        audit.record(actor=actor, action="artwork.primary_image_changed", entity=artwork)
    return image


@transaction.atomic
def delete_image(image: ArtworkImage, *, actor) -> None:
    artwork = _lock(image.artwork)
    others = artwork.images.exclude(pk=image.pk)
    if (
        artwork.publication_status == PublicationStatus.PUBLISHED
        and not others.filter(asset__status=ImageStatus.READY).exists()
    ):
        raise LastImageError()
    was_primary = image.is_primary
    asset = image.asset
    image.delete()
    if was_primary:
        replacement = (
            others.filter(asset__status=ImageStatus.READY).order_by("sort_order", "id").first()
            or others.order_by("sort_order", "id").first()
        )
        if replacement:
            replacement.is_primary = True
            replacement.save(update_fields=["is_primary"])
    media.delete_asset(asset)
    audit.record(actor=actor, action="artwork.image_deleted", entity=artwork)

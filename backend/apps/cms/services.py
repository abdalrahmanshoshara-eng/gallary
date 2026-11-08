"""Content workflow (F-CMS). Every publish and edit is audited."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.media import services as media
from apps.media.models import ImagePurpose

from .models import Banner, FaqItem, FeaturedArtwork, Page, PageSlug, PageVersion

MAX_FEATURED = 12


def _invalid(field: str, message: str) -> ConflictError:
    return ConflictError(message, code="VALIDATION_ERROR", http_status=400, details={field: [message]})


# --- pages (F-CMS-01, BR-313) --------------------------------------------------------------------
def page(slug: str) -> Page:
    obj, _ = Page.objects.get_or_create(slug=slug)
    return obj


@transaction.atomic
def save_draft(page_obj: Page, *, actor, title: str, body: str) -> Page:
    page_obj = Page.objects.select_for_update().get(pk=page_obj.pk)
    page_obj.draft_title = title.strip()
    page_obj.draft_body = body.strip()
    page_obj.draft_updated_at = timezone.now()
    page_obj.draft_updated_by = actor
    page_obj.save()
    audit.record(actor=actor, action="page.draft_saved", entity_type="cms.page", entity_id=page_obj.slug)
    return page_obj


def has_unpublished_changes(page_obj: Page) -> bool:
    current = page_obj.published
    if current is None:
        return bool(page_obj.draft_title or page_obj.draft_body)
    return (page_obj.draft_title, page_obj.draft_body) != (current.title, current.body)


def _next_code(page_obj: Page) -> str:
    base = timezone.localdate().isoformat()
    taken = set(page_obj.versions.filter(code__startswith=base).values_list("code", flat=True))
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


@transaction.atomic
def publish(page_obj: Page, *, actor) -> PageVersion:
    """The draft becomes a new immutable version (what visitors and customers see)."""
    page_obj = Page.objects.select_for_update().get(pk=page_obj.pk)
    if not page_obj.draft_title.strip():
        raise _invalid("title", "العنوان مطلوب.")
    if not page_obj.draft_body.strip():
        raise _invalid("body", "نص الصفحة مطلوب.")
    if not has_unpublished_changes(page_obj):
        raise ConflictError("لا توجد تعديلات جديدة للنشر.", code="NOTHING_TO_PUBLISH")
    number = (page_obj.versions.aggregate(m=Max("number"))["m"] or 0) + 1
    version = PageVersion.objects.create(
        page=page_obj,
        number=number,
        code=_next_code(page_obj),
        title=page_obj.draft_title,
        body=page_obj.draft_body,
        published_by=actor,
    )
    page_obj.published = version
    page_obj.save(update_fields=["published"])
    audit.record(
        actor=actor,
        action="page.published",
        entity_type="cms.page",
        entity_id=page_obj.slug,
        changes={"version": {"from": number - 1 or None, "to": number}, "code": version.code},
    )
    return version


def published_policy() -> PageVersion | None:
    """The deposit policy customers accept at checkout (BR-313), or None before it is published."""
    page_obj = Page.objects.select_related("published").filter(slug=PageSlug.DEPOSIT_POLICY).first()
    return page_obj.published if page_obj else None


# --- ordering helper --------------------------------------------------------------------------------
def _move(qs, obj, direction: str) -> None:
    """Swap with the neighbour (up = earlier). Renumbers first so orders are always distinct."""
    items = list(qs.select_for_update().order_by("sort_order", "id"))
    for index, item in enumerate(items):
        if item.sort_order != index:
            item.sort_order = index
            item.save(update_fields=["sort_order"])
    index = next(i for i, item in enumerate(items) if item.pk == obj.pk)
    target = index - 1 if direction == "up" else index + 1
    if not 0 <= target < len(items):
        return
    a, b = items[index], items[target]
    a.sort_order, b.sort_order = b.sort_order, a.sort_order
    a.save(update_fields=["sort_order"])
    b.save(update_fields=["sort_order"])


def _next_order(model) -> int:
    return (model.objects.aggregate(m=Max("sort_order"))["m"] or 0) + 1


# --- FAQ (F-CMS-02) --------------------------------------------------------------------------------
@transaction.atomic
def save_faq(item: FaqItem | None, *, actor, data: dict) -> FaqItem:
    question, answer = data.get("question", "").strip(), data.get("answer", "").strip()
    if (item is None or "question" in data) and not question:
        raise _invalid("question", "السؤال مطلوب.")
    if (item is None or "answer" in data) and not answer:
        raise _invalid("answer", "الإجابة مطلوبة.")
    if item is None:
        item = FaqItem(sort_order=_next_order(FaqItem))
    for field in ("question", "answer"):
        if field in data:
            setattr(item, field, data[field].strip())
    if "is_active" in data:
        item.is_active = data["is_active"]
    item.save()
    audit.record(
        actor=actor, action="faq.saved", entity=item, changes={"question": item.question, "active": item.is_active}
    )
    return item


@transaction.atomic
def delete_faq(item: FaqItem, *, actor) -> None:
    audit.record(actor=actor, action="faq.deleted", entity=item, changes={"question": item.question})
    item.delete()


@transaction.atomic
def move_faq(item: FaqItem, direction: str) -> None:
    _move(FaqItem.objects.all(), item, direction)


# --- banners (F-CMS-03) ----------------------------------------------------------------------------
def _check_link(url: str, label: str) -> None:
    if url and not (url.startswith("https://") or (url.startswith("/") and not url.startswith("//"))):
        raise _invalid("link_url", "الرابط يبدأ بـ / لصفحة داخلية أو https:// لموقع خارجي.")
    if url and not label:
        raise _invalid("link_label", "اكتب نص الزر للرابط.")


@transaction.atomic
def save_banner(banner: Banner | None, *, actor, data: dict, image=None) -> Banner:
    creating = banner is None
    banner = banner or Banner(sort_order=_next_order(Banner))
    for field in ("title", "subtitle", "link_url", "link_label", "is_active", "starts_at", "ends_at"):
        if field in data:
            value = data[field]
            setattr(banner, field, value.strip() if isinstance(value, str) else value)
    if not banner.title:
        raise _invalid("title", "العنوان مطلوب.")
    _check_link(banner.link_url, banner.link_label)
    if banner.starts_at and banner.ends_at and banner.ends_at <= banner.starts_at:
        raise _invalid("ends_at", "نهاية العرض بعد بدايته.")
    if creating and image is None:
        raise _invalid("image", "صورة البنر مطلوبة.")
    old = banner.image if image is not None else None
    if image is not None:
        banner.image = media.ingest_image(image, purpose=ImagePurpose.BANNER, user=actor)
    banner.save()
    if old is not None:
        media.delete_asset(old)
    audit.record(
        actor=actor,
        action="banner.created" if creating else "banner.updated",
        entity=banner,
        changes={"title": banner.title},
    )
    return banner


@transaction.atomic
def delete_banner(banner: Banner, *, actor) -> None:
    audit.record(actor=actor, action="banner.deleted", entity=banner, changes={"title": banner.title})
    image = banner.image
    banner.delete()
    if image is not None:
        media.delete_asset(image)


@transaction.atomic
def move_banner(banner: Banner, direction: str) -> None:
    _move(Banner.objects.all(), banner, direction)


def banner_state(banner: Banner, now=None) -> str:
    now = now or timezone.now()
    if not banner.is_active:
        return "hidden"
    if banner.starts_at and banner.starts_at > now:
        return "scheduled"
    if banner.ends_at and banner.ends_at <= now:
        return "expired"
    return "live"


# --- featured artworks (F-CMS-03) --------------------------------------------------------------------
@transaction.atomic
def add_featured(artwork, *, actor) -> FeaturedArtwork:
    from apps.artworks.models import PublicationStatus

    if artwork.publication_status != PublicationStatus.PUBLISHED or artwork.archived_at is not None:
        raise _invalid("artwork", "تُختار الأعمال المنشورة غير المؤرشفة فقط.")
    if FeaturedArtwork.objects.filter(artwork=artwork).exists():
        raise ConflictError("هذا العمل ضمن المختارات بالفعل.", code="ALREADY_FEATURED")
    if FeaturedArtwork.objects.count() >= MAX_FEATURED:
        raise ConflictError(f"الحد الأقصى {MAX_FEATURED} عملاً مختاراً.", code="FEATURED_LIMIT")
    item = FeaturedArtwork.objects.create(artwork=artwork, sort_order=_next_order(FeaturedArtwork), added_by=actor)
    audit.record(actor=actor, action="featured.added", entity=artwork)
    return item


@transaction.atomic
def remove_featured(item: FeaturedArtwork, *, actor) -> None:
    audit.record(actor=actor, action="featured.removed", entity=item.artwork)
    item.delete()


@transaction.atomic
def move_featured(item: FeaturedArtwork, direction: str) -> None:
    _move(FeaturedArtwork.objects.all(), item, direction)

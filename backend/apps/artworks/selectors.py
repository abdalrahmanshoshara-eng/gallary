"""
Read paths. Every public rule about visibility lives here (one place, one definition):

    visible  = PUBLISHED and (no artist or artist is ACTIVE)
    catalog  = visible and not archived
    archive  = visible and archived and archive_visibility = VISIBLE
    detail   = catalog ∪ archive
"""

from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet

from apps.artists.models import ArtistStatus
from apps.catalog.selectors import category_with_descendants

from .models import ArchiveVisibility, Artwork, ArtworkImage, PublicationStatus

ORDERINGS = {
    "newest": ("-published_at", "-id"),
    "oldest": ("published_at", "id"),
    "title": ("title", "id"),
    "year": ("-year_created", "-published_at"),
}


def public_artwork_filter(prefix: str = "") -> Q:
    """Visible-to-the-public condition, reusable from related models (e.g. artist counts)."""
    p = prefix
    return (
        Q(**{f"{p}publication_status": PublicationStatus.PUBLISHED})
        & (Q(**{f"{p}artist__isnull": True}) | Q(**{f"{p}artist__status": ArtistStatus.ACTIVE}))
        & (Q(**{f"{p}archived_at__isnull": True}) | Q(**{f"{p}archive_visibility": ArchiveVisibility.VISIBLE}))
    )


def _with_cards(qs: QuerySet[Artwork]) -> QuerySet[Artwork]:
    primary = ArtworkImage.objects.filter(is_primary=True).select_related("asset")
    return qs.select_related("category", "artist").prefetch_related(
        Prefetch("images", queryset=primary, to_attr="primary_images")
    )


def _visible() -> QuerySet[Artwork]:
    return Artwork.objects.filter(public_artwork_filter())


def catalog_artworks(*, category: str = "", artist: str = "", ordering: str = "newest") -> QuerySet[Artwork]:
    qs = _visible().filter(archived_at__isnull=True)
    if category:
        qs = qs.filter(category_id__in=category_with_descendants(category))
    if artist:
        qs = qs.filter(artist__slug=artist)
    return _with_cards(qs).order_by(*ORDERINGS.get(ordering, ORDERINGS["newest"]))


def archive_artworks(*, artist: str = "") -> QuerySet[Artwork]:
    qs = _visible().filter(archived_at__isnull=False)
    if artist:
        qs = qs.filter(artist__slug=artist)
    return _with_cards(qs).order_by("-archived_at", "-id")


def public_artwork_detail() -> QuerySet[Artwork]:
    images = ArtworkImage.objects.filter(asset__status="ready").select_related("asset").order_by("sort_order", "id")
    return (
        _visible()
        .select_related("category", "category__parent", "artist", "executor")
        .prefetch_related(
            "materials",
            "techniques",
            "tags",
            Prefetch("images", queryset=images, to_attr="ready_images"),
        )
    )


def admin_artworks(*, search: str = "", status: str = "", category: str = "", artist: str = "", archived: str = ""):
    qs = Artwork.objects.select_related("category", "artist").prefetch_related(
        Prefetch(
            "images",
            queryset=ArtworkImage.objects.filter(is_primary=True).select_related("asset"),
            to_attr="primary_images",
        )
    )
    if status:
        qs = qs.filter(publication_status=status)
    if category:
        qs = qs.filter(category__slug=category)
    if artist:
        qs = qs.filter(artist__public_id=artist)
    if archived == "true":
        qs = qs.filter(archived_at__isnull=False)
    elif archived == "false":
        qs = qs.filter(archived_at__isnull=True)
    if search.strip():
        term = search.strip()
        qs = qs.filter(
            Q(title__icontains=term) | Q(artist__name__icontains=term) | Q(creator_name_override__icontains=term)
        )
    return qs.order_by("-updated_at")


def admin_artwork_detail() -> QuerySet[Artwork]:
    return Artwork.objects.select_related("category", "artist", "executor", "owner_user").prefetch_related(
        "materials",
        "techniques",
        "tags",
        Prefetch("images", queryset=ArtworkImage.objects.select_related("asset").order_by("sort_order", "id")),
    )

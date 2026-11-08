from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from apps.artworks.models import ArtworkImage, PublicationStatus

from .models import Banner, FaqItem, FeaturedArtwork, Page


def published_pages() -> QuerySet[Page]:
    return Page.objects.filter(published__isnull=False).select_related("published")


def live_banners() -> QuerySet[Banner]:
    now = timezone.now()
    return (
        Banner.objects.filter(is_active=True, image__status="ready")
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .select_related("image")
    )


def public_faq() -> QuerySet[FaqItem]:
    return FaqItem.objects.filter(is_active=True)


def featured_items() -> QuerySet[FeaturedArtwork]:
    primary = ArtworkImage.objects.filter(is_primary=True).select_related("asset")
    return FeaturedArtwork.objects.select_related("artwork__artist").prefetch_related(
        Prefetch("artwork__images", queryset=primary, to_attr="primary_images")
    )


def public_featured_artworks():
    """Curated artworks still public (hidden or archived works drop out by themselves)."""
    from apps.listings.selectors import with_offers

    ids = [
        f.artwork_id
        for f in FeaturedArtwork.objects.filter(
            artwork__publication_status=PublicationStatus.PUBLISHED, artwork__archived_at__isnull=True
        ).order_by("sort_order", "id")
    ]
    from apps.artworks.models import Artwork

    primary = ArtworkImage.objects.filter(is_primary=True).select_related("asset")
    artworks = with_offers(
        Artwork.objects.filter(pk__in=ids)
        .select_related("artist", "category")
        .prefetch_related(Prefetch("images", queryset=primary, to_attr="primary_images"))
    )
    order = {pk: index for index, pk in enumerate(ids)}
    return sorted(artworks, key=lambda a: order[a.pk])

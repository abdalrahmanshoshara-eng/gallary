from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from .models import Artist, ArtistStatus


def _published_count():
    # Imported lazily to avoid an app-level import cycle (artworks → artists).
    from apps.artworks.selectors import public_artwork_filter

    return Count("artworks", filter=public_artwork_filter(prefix="artworks__"), distinct=True)


def public_artists() -> QuerySet[Artist]:
    return (
        Artist.objects.filter(status=ArtistStatus.ACTIVE)
        .select_related("photo")
        .annotate(artwork_count=_published_count())
        .order_by("-is_featured", "name")
    )


def admin_artists(*, search: str = "", status: str = "") -> QuerySet[Artist]:
    qs = Artist.objects.select_related("photo").annotate(artwork_count=Count("artworks", distinct=True))
    if status:
        qs = qs.filter(status=status)
    if search.strip():
        term = search.strip()
        qs = qs.filter(Q(name__icontains=term) | Q(city__icontains=term) | Q(contact_phone__icontains=term))
    return qs.order_by("name")

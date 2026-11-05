"""
Storefront read paths: the public catalogue with search (§21) and the offer of each artwork.

`storefront_artworks` is the single search/filter entry point (ARCHITECTURE risk 12): it can
later be backed by a dedicated engine without changing the API.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Exists, F, OuterRef, Prefetch, Q, QuerySet, Subquery
from django.utils import timezone

from apps.artworks import selectors as artwork_selectors
from apps.artworks.models import Artwork
from apps.core.arabic import search_terms

from .models import Listing, ListingStatus, QuantityMode, SaleMode

SHOWN_STATUSES = (ListingStatus.ACTIVE, ListingStatus.SOLD_OUT)


def with_offers(qs: QuerySet[Artwork]) -> QuerySet[Artwork]:
    return qs.prefetch_related(
        Prefetch(
            "listings",
            # `auction`: reverse one-to-one used by the offer's auction link (no query per card).
            queryset=Listing.objects.filter(status__in=SHOWN_STATUSES).select_related("auction"),
            to_attr="shown_listings",
        )
    )


def pick_offer(artwork: Artwork) -> Listing | None:
    listings = getattr(artwork, "shown_listings", None)
    if listings is None:
        listings = list(Listing.objects.filter(artwork=artwork, status__in=SHOWN_STATUSES))
    active = [x for x in listings if x.status == ListingStatus.ACTIVE]
    if active:
        return active[0]
    sold = sorted((x for x in listings), key=lambda x: x.closed_at or x.created_at, reverse=True)
    return sold[0] if sold else None


def _buyable_now() -> Q:
    now = timezone.now()
    return (
        Q(status=ListingStatus.ACTIVE, sale_mode=SaleMode.FIXED_PRICE)
        & (Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        & (Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        & (Q(quantity_mode=QuantityMode.UNLIMITED) | Q(quantity_available__gt=0))
    )


def _decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number >= 0 else None


ORDERINGS = {
    **artwork_selectors.ORDERINGS,
    "price_asc": ("current_price", "-published_at"),
    "price_desc": ("-current_price", "-published_at"),
}


def storefront_artworks(
    *,
    q: str = "",
    category: str = "",
    artist: str = "",
    materials: list[str] | None = None,
    techniques: list[str] | None = None,
    price_min: str = "",
    price_max: str = "",
    availability: str = "",
    sale_mode: str = "",
    ordering: str = "newest",
) -> QuerySet[Artwork]:
    qs = artwork_selectors.catalog_artworks(category=category, artist=artist, ordering="newest")

    for term in search_terms(q):
        qs = qs.filter(search_text__contains=term)  # served by the trigram GIN index
    for slug in materials or []:
        qs = qs.filter(materials__slug=slug)
    for slug in techniques or []:
        qs = qs.filter(techniques__slug=slug)

    active = Listing.objects.filter(artwork=OuterRef("pk"), status=ListingStatus.ACTIVE)
    qs = qs.annotate(current_price=Subquery(active.values("price_usd")[:1]))
    low, high = _decimal(price_min), _decimal(price_max)
    if low is not None:
        qs = qs.filter(current_price__gte=low)
    if high is not None:
        qs = qs.filter(current_price__lte=high)
    if sale_mode in SaleMode.values:
        qs = qs.filter(Exists(active.filter(sale_mode=sale_mode)))
    if availability == "available":
        qs = qs.filter(Exists(Listing.objects.filter(_buyable_now(), artwork=OuterRef("pk"))))
    elif availability == "unavailable":
        qs = qs.exclude(Exists(Listing.objects.filter(_buyable_now(), artwork=OuterRef("pk"))))

    order = ORDERINGS.get(ordering, ORDERINGS["newest"])
    if ordering in ("price_asc", "price_desc"):
        first = (
            F("current_price").asc(nulls_last=True)
            if ordering == "price_asc"
            else F("current_price").desc(nulls_last=True)
        )
        return with_offers(qs).order_by(first, "-published_at", "-id")
    return with_offers(qs).order_by(*order)


def admin_listings_for(artwork: Artwork) -> QuerySet[Listing]:
    return Listing.objects.filter(artwork=artwork).select_related("pricing_approved_by").order_by("-created_at")

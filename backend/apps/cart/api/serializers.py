from __future__ import annotations

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artworks.api.serializers import PublicArtworkImageSerializer, _primary
from apps.core.models import SiteSetting
from apps.listings import services as listing_services

from .. import services


class CartLineSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="item.public_id")
    listing = serializers.UUIDField(source="item.listing.public_id")
    artwork_slug = serializers.CharField(source="item.listing.artwork.slug")
    title = serializers.CharField(source="item.listing.artwork.title")
    creator_name = serializers.CharField(source="item.listing.artwork.creator_display")
    image = serializers.SerializerMethodField()
    quantity = serializers.IntegerField(source="item.quantity")
    max_quantity = serializers.SerializerMethodField()
    quantity_mode = serializers.CharField(source="item.listing.quantity_mode")
    unit_price = serializers.DecimalField(
        source="item.listing.price_usd", max_digits=12, decimal_places=2, allow_null=True
    )
    price_at_add = serializers.DecimalField(source="item.price_at_add", max_digits=12, decimal_places=2)
    price_changed = serializers.BooleanField()
    line_total = serializers.SerializerMethodField()
    deposit = serializers.SerializerMethodField()
    problem = serializers.CharField(allow_null=True, help_text="Why this line cannot be ordered now; null when it can.")

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_image(self, state):
        return _primary(state.item.listing.artwork)

    def get_max_quantity(self, state) -> int:
        return services.max_quantity(state.item.listing)

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_line_total(self, state):
        price = state.item.listing.price_usd or Decimal(0)
        return f"{price * state.item.quantity:.2f}"

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_deposit(self, state):
        listing = state.item.listing
        total = (listing.price_usd or Decimal(0)) * state.item.quantity
        terms = listing_services.deposit_terms(listing, self.context["settings"])
        return f"{terms.amount_for(total, state.item.quantity):.2f}"


class CartSerializer(serializers.Serializer):
    lines = CartLineSerializer(many=True)
    count = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Orderable lines only")
    deposit_due = serializers.DecimalField(max_digits=12, decimal_places=2)
    remaining_after_deposit = serializers.DecimalField(max_digits=12, decimal_places=2)
    can_checkout = serializers.BooleanField()
    blocking = serializers.ListField(child=serializers.CharField(), help_text="price_changed / unavailable / empty")
    max_items = serializers.IntegerField()


def cart_payload(user) -> dict:
    settings_row = SiteSetting.load()
    states = services.line_states(services.get_cart(user))
    context = {"settings": settings_row}
    lines = CartLineSerializer(states, many=True, context=context).data
    ok = [line for line in lines if line["problem"] is None]
    blocking = []
    if not states:
        blocking.append("empty")
    if any(s.problem for s in states):
        blocking.append("unavailable")
    if any(s.price_changed and not s.problem for s in states):
        blocking.append("price_changed")
    subtotal = sum((Decimal(line["line_total"]) for line in ok), Decimal(0))
    deposit = min(sum((Decimal(line["deposit"]) for line in ok), Decimal(0)), subtotal)
    return {
        "lines": lines,
        "count": len(states),
        "subtotal": f"{subtotal:.2f}",
        "deposit_due": f"{deposit:.2f}",
        "remaining_after_deposit": f"{subtotal - deposit:.2f}",
        "can_checkout": not blocking,
        "blocking": blocking,
        "max_items": services.MAX_ITEMS,
    }


class AddToCartSerializer(serializers.Serializer):
    listing = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=100, default=1)


class QuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class CartCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()

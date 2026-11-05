from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artworks.api.serializers import PublicArtworkCardSerializer, PublicArtworkDetailSerializer
from apps.core.models import DepositType, SiteSetting

from .. import selectors, services
from ..models import Listing, QuantityMode


class PublicOfferSerializer(serializers.Serializer):
    """What a visitor needs to decide: price, availability and why it can't be bought."""

    id = serializers.UUIDField(source="public_id")
    sale_mode = serializers.CharField()
    status = serializers.CharField()
    price_usd = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    quantity_mode = serializers.CharField()
    available = serializers.SerializerMethodField(help_text="Units left; null when stock is not tracked.")
    max_per_order = serializers.IntegerField()
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    purchasable = serializers.SerializerMethodField()
    unavailable_reason = serializers.SerializerMethodField()
    auction_id = serializers.SerializerMethodField(help_text="Set when the offer is an auction: link to its page.")

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_auction_id(self, listing: Listing):
        auction = getattr(listing, "auction", None)  # reverse one-to-one; listings never import auctions
        return str(auction.public_id) if auction is not None else None

    def get_available(self, listing: Listing) -> int | None:
        return None if listing.quantity_mode == QuantityMode.UNLIMITED else listing.quantity_available

    def get_purchasable(self, listing: Listing) -> bool:
        return services.purchase_problem(listing) is None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_unavailable_reason(self, listing: Listing) -> str | None:
        return services.purchase_problem(listing)


def _offer(artwork):
    listing = selectors.pick_offer(artwork)
    if listing is None:
        return None
    listing.artwork = artwork  # avoid re-fetching for the availability check
    return PublicOfferSerializer(listing).data


class StorefrontCardSerializer(PublicArtworkCardSerializer):
    offer = serializers.SerializerMethodField()

    class Meta(PublicArtworkCardSerializer.Meta):
        fields = [*PublicArtworkCardSerializer.Meta.fields, "offer"]
        read_only_fields = fields

    @extend_schema_field(PublicOfferSerializer(allow_null=True))
    def get_offer(self, artwork):
        return _offer(artwork)


class StorefrontDetailSerializer(PublicArtworkDetailSerializer):
    offer = serializers.SerializerMethodField()

    class Meta(PublicArtworkDetailSerializer.Meta):
        fields = [*PublicArtworkDetailSerializer.Meta.fields, "offer"]
        read_only_fields = fields

    @extend_schema_field(PublicOfferSerializer(allow_null=True))
    def get_offer(self, artwork):
        return _offer(artwork)


# --- staff ----------------------------------------------------------------------------------------
class DepositTermsSerializer(serializers.Serializer):
    type = serializers.CharField()
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    inherited = serializers.BooleanField()


class AdminListingSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    artwork = serializers.UUIDField(source="artwork.public_id", read_only=True)
    pricing_approved_by = serializers.CharField(source="pricing_approved_by.display_name", read_only=True, default=None)
    effective_commission_rate = serializers.SerializerMethodField()
    effective_deposit = serializers.SerializerMethodField()
    activation_problems = serializers.SerializerMethodField()
    purchasable = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "artwork",
            "sale_mode",
            "status",
            "price_usd",
            "commission_rate_override",
            "deposit_type",
            "deposit_value",
            "pricing_approved_by",
            "pricing_approved_at",
            "effective_commission_rate",
            "effective_deposit",
            "quantity_mode",
            "quantity_total",
            "quantity_available",
            "quantity_reserved",
            "quantity_sold",
            "max_per_order",
            "starts_at",
            "ends_at",
            "activated_at",
            "closed_at",
            "internal_notes",
            "activation_problems",
            "purchasable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(max_digits=5, decimal_places=2))
    def get_effective_commission_rate(self, listing: Listing):
        return f"{services.commission_rate(listing, self.context.get('settings')):.2f}"

    @extend_schema_field(DepositTermsSerializer)
    def get_effective_deposit(self, listing: Listing):
        terms = services.deposit_terms(listing, self.context.get("settings"))
        return {"type": terms.type, "value": f"{terms.value:.2f}", "inherited": not listing.deposit_type}

    def get_activation_problems(self, listing: Listing) -> list[str]:
        return services.activation_problems(listing) if listing.status == "draft" else []

    def get_purchasable(self, listing: Listing) -> bool:
        return services.purchase_problem(listing) is None


class ListingWriteSerializer(serializers.Serializer):
    quantity_mode = serializers.ChoiceField(choices=QuantityMode.choices, required=False)
    quantity_total = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    max_per_order = serializers.IntegerField(min_value=1, max_value=100, required=False)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    internal_notes = serializers.CharField(required=False, allow_blank=True)


class PricingSerializer(serializers.Serializer):
    price_usd = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    commission_rate_override = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, allow_null=True, default=None
    )
    deposit_type = serializers.ChoiceField(choices=DepositType.choices, required=False, allow_blank=True, default="")
    deposit_value = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True, default=None
    )


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class SiteSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSetting
        fields = [
            "default_commission_rate",
            "default_deposit_type",
            "default_deposit_value",
            "whatsapp_number",
            "max_pending_orders_per_user",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate(self, attrs):
        deposit_type = attrs.get("default_deposit_type", getattr(self.instance, "default_deposit_type", None))
        value = attrs.get("default_deposit_value", getattr(self.instance, "default_deposit_value", None))
        if value is not None and value <= 0:
            raise serializers.ValidationError({"default_deposit_value": ["قيمة العربون يجب أن تكون أكبر من صفر."]})
        if deposit_type == DepositType.PERCENTAGE and value is not None and value > 100:
            raise serializers.ValidationError({"default_deposit_value": ["نسبة العربون لا تتجاوز 100%."]})
        return attrs

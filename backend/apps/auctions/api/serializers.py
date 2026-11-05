from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artworks.api.serializers import PublicArtworkImageSerializer, _primary
from apps.catalog.models import Category
from apps.media.serializers import AdminImageSerializer

from ..models import Auction, AuctionRequest, Bid, NonPaymentPolicy, RequestStatus


class AuctionCardSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    artwork_slug = serializers.CharField(source="listing.artwork.slug")
    creator_name = serializers.CharField(source="listing.artwork.creator_display")
    image = serializers.SerializerMethodField()
    minimum_next_bid = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = Auction
        fields = [
            "id",
            "title",
            "artwork_slug",
            "creator_name",
            "image",
            "status",
            "outcome",
            "starting_price",
            "current_price",
            "minimum_next_bid",
            "bid_count",
            "starts_at",
            "ends_at",
        ]
        read_only_fields = fields

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_image(self, auction: Auction):
        return _primary(auction.listing.artwork)


class AuctionDetailSerializer(AuctionCardSerializer):
    description = serializers.CharField(source="listing.artwork.description")
    images = serializers.SerializerMethodField()
    reserve_met = serializers.SerializerMethodField(
        help_text="null when there is no reserve; the reserve itself stays private"
    )

    class Meta(AuctionCardSerializer.Meta):
        fields = [
            *AuctionCardSerializer.Meta.fields,
            "description",
            "images",
            "terms",
            "minimum_increment",
            "extension_window_sec",
            "extension_duration_sec",
            "max_extensions",
            "extensions_count",
            "winner_deposit_percent",
            "winner_payment_window_sec",
            "non_payment_policy",
            "reserve_met",
            "version",
        ]
        read_only_fields = fields

    @extend_schema_field(PublicArtworkImageSerializer(many=True))
    def get_images(self, auction: Auction):
        from apps.media.serializers import PublicImageSerializer

        return [
            {"id": i.public_id, "alt_text": i.alt_text, "image": PublicImageSerializer(i.asset).data}
            for i in auction.listing.artwork.images.all()
            if i.asset.is_ready
        ]

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_reserve_met(self, auction: Auction):
        if auction.reserve_price is None:
            return None
        return auction.current_price is not None and auction.current_price >= auction.reserve_price


class PublicBidSerializer(serializers.Serializer):
    """A bid as every viewer sees it: amount and a stable per-auction alias, never identity (BR-509)."""

    id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    alias = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class MyAuctionStateSerializer(serializers.Serializer):
    alias = serializers.IntegerField(allow_null=True)
    my_top_bid = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    is_highest = serializers.BooleanField()
    is_winner = serializers.BooleanField()
    order_number = serializers.CharField(allow_null=True)
    can_bid = serializers.BooleanField()


class AuctionSnapshotSerializer(serializers.Serializer):
    """The WebSocket snapshot (ARCHITECTURE §5.4); the REST resync adds `me`."""

    seq = serializers.IntegerField()
    server_time = serializers.DateTimeField()
    status = serializers.CharField()
    outcome = serializers.CharField()
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    minimum_next_bid = serializers.DecimalField(max_digits=12, decimal_places=2)
    bid_count = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    extensions_count = serializers.IntegerField()
    reserve_met = serializers.BooleanField(allow_null=True, help_text="null without a reserve")
    payment_deadline = serializers.DateTimeField(allow_null=True)
    winner_alias = serializers.IntegerField(allow_null=True)
    bids = PublicBidSerializer(many=True)


class AuctionStateSerializer(AuctionSnapshotSerializer):
    me = MyAuctionStateSerializer(allow_null=True)


class BidInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class BidResultSerializer(serializers.Serializer):
    bid = PublicBidSerializer()
    state = AuctionStateSerializer()
    replayed = serializers.BooleanField()


class MyBidAuctionSerializer(AuctionCardSerializer):
    my_top_bid = serializers.DecimalField(max_digits=12, decimal_places=2)
    my_status = serializers.CharField(help_text="highest / outbid / won / lost / pending_payment / unpaid")
    order_number = serializers.CharField(allow_null=True)

    class Meta(AuctionCardSerializer.Meta):
        fields = [*AuctionCardSerializer.Meta.fields, "my_top_bid", "my_status", "order_number"]
        read_only_fields = fields


# --- staff ----------------------------------------------------------------------------------------------
class AuctionWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=250, required=False)
    terms = serializers.CharField(required=False, allow_blank=True)
    starting_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    minimum_increment = serializers.DecimalField(max_digits=12, decimal_places=2)
    reserve_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    extension_window_sec = serializers.IntegerField(min_value=0, max_value=3600, required=False)
    extension_duration_sec = serializers.IntegerField(min_value=0, max_value=3600, required=False)
    max_extensions = serializers.IntegerField(min_value=0, max_value=50, required=False)
    winner_deposit_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    non_payment_policy = serializers.ChoiceField(choices=NonPaymentPolicy.choices, required=False)


class EligibleArtworkSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    title = serializers.CharField()
    creator_name = serializers.CharField(source="creator_display")
    image = serializers.SerializerMethodField()

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_image(self, artwork):
        return _primary(artwork)


class AuctionCreateSerializer(AuctionWriteSerializer):
    artwork = serializers.UUIDField()
    request = serializers.UUIDField(required=False, allow_null=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)


class AdminBidSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    alias = serializers.IntegerField(source="bidder_alias")
    created_at = serializers.DateTimeField()
    status = serializers.CharField()
    bidder = serializers.SerializerMethodField()
    bidder_phone = serializers.CharField(source="user.phone")

    def get_bidder(self, bid: Bid) -> str:
        return bid.user.display_name or bid.user.phone


class AdminAuctionSerializer(AuctionDetailSerializer):
    artwork_id = serializers.UUIDField(source="listing.artwork.public_id")
    commission_rate = serializers.DecimalField(
        source="listing.commission_rate_override", max_digits=5, decimal_places=2, allow_null=True
    )
    bids = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    winner_order = serializers.SerializerMethodField()
    schedule_problems = serializers.SerializerMethodField()
    editable = serializers.SerializerMethodField()

    class Meta(AuctionDetailSerializer.Meta):
        fields = [
            *AuctionDetailSerializer.Meta.fields,
            "artwork_id",
            "reserve_price",
            "original_ends_at",
            "commission_rate",
            "winner_declared_at",
            "payment_deadline",
            "cancelled_reason",
            "bids",
            "history",
            "winner_order",
            "schedule_problems",
            "editable",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminBidSerializer(many=True))
    def get_bids(self, auction: Auction):
        return AdminBidSerializer(auction.bids.select_related("user").order_by("-created_at")[:200], many=True).data

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_history(self, auction: Auction):
        return [
            {
                "to_status": h.to_status,
                "reason": h.reason,
                "actor": h.actor.display_name if h.actor else None,
                "at": h.created_at,
            }
            for h in auction.history.select_related("actor")
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_winner_order(self, auction: Auction):
        from apps.orders.models import Order

        if not auction.winner_order_id:
            return None
        return Order.objects.filter(pk=auction.winner_order_id).values_list("order_number", flat=True).first()

    def get_schedule_problems(self, auction: Auction) -> list[str]:
        from .. import services

        return services.schedule_problems(auction) if auction.status == "draft" else []

    def get_editable(self, auction: Auction) -> bool:
        return auction.status in ("draft", "scheduled") and timezone.now() < auction.starts_at


class AuctionReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, allow_blank=True)


# --- auction requests ---------------------------------------------------------------------------------
class RequestNoteSerializer(serializers.Serializer):
    body = serializers.CharField()
    visibility = serializers.CharField()
    author = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class AuctionRequestSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    images = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField(help_text="Messages from the platform to the customer")
    history = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_withdraw = serializers.SerializerMethodField()
    auction_id = serializers.UUIDField(source="resulting_auction.public_id", allow_null=True, read_only=True)

    class Meta:
        model = AuctionRequest
        fields = [
            "id",
            "work_title",
            "work_description",
            "artist_name",
            "artist_info",
            "category_hint",
            "dimensions_text",
            "year_text",
            "expected_price",
            "customer_notes",
            "status",
            "images",
            "messages",
            "history",
            "can_edit",
            "can_withdraw",
            "auction_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminImageSerializer(many=True))
    def get_images(self, req: AuctionRequest):
        return [AdminImageSerializer(i.asset).data for i in req.images.select_related("asset")]

    @extend_schema_field(RequestNoteSerializer(many=True))
    def get_messages(self, req: AuctionRequest):
        return [
            {"body": n.body, "visibility": n.visibility, "author": None, "created_at": n.created_at}
            for n in req.notes.filter(visibility="customer")
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_history(self, req: AuctionRequest):
        return [{"status": h.to_status, "at": h.created_at} for h in req.history.all()]

    def get_can_edit(self, req: AuctionRequest) -> bool:
        return req.status == RequestStatus.NEEDS_MORE_INFO

    def get_can_withdraw(self, req: AuctionRequest) -> bool:
        return req.status not in ("approved", "rejected", "withdrawn")


class AdminAuctionRequestSerializer(AuctionRequestSerializer):
    customer = serializers.CharField(source="user.display_name")
    customer_email = serializers.CharField(source="user.email")
    artwork_id = serializers.UUIDField(source="resulting_artwork.public_id", allow_null=True, read_only=True)
    actions = serializers.SerializerMethodField()
    contact_phone = serializers.CharField()
    agreed_commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    commission_agreed_at = serializers.DateTimeField(allow_null=True)
    notes = serializers.SerializerMethodField()

    class Meta(AuctionRequestSerializer.Meta):
        fields = [
            *AuctionRequestSerializer.Meta.fields,
            "customer",
            "customer_email",
            "contact_phone",
            "agreed_commission_rate",
            "commission_agreed_at",
            "artwork_id",
            "notes",
            "actions",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions(self, req: AuctionRequest):
        """Moves staff can make now: target statuses, set_commission, create_artwork, create_auction."""
        from ..requests import STAFF_TRANSITIONS

        actions = [str(to) for to in STAFF_TRANSITIONS.get(req.status, ())]
        if req.status == RequestStatus.NEGOTIATION:
            actions.append("set_commission")
            if req.agreed_commission_rate is not None:
                actions.append("approved")
        if req.status == RequestStatus.APPROVED:
            if req.resulting_artwork_id is None:
                actions.append("create_artwork")
            elif req.resulting_auction_id is None:
                actions.append("create_auction")
        return sorted(actions)

    @extend_schema_field(RequestNoteSerializer(many=True))
    def get_notes(self, req: AuctionRequest):
        return [
            {
                "body": n.body,
                "visibility": n.visibility,
                "author": n.author.display_name if n.author else None,
                "created_at": n.created_at,
            }
            for n in req.notes.select_related("author")
        ]


class AuctionRequestInputSerializer(serializers.Serializer):
    work_title = serializers.CharField(max_length=250)
    work_description = serializers.CharField(max_length=5000)
    artist_name = serializers.CharField(max_length=200)
    artist_info = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    category_hint = serializers.CharField(max_length=120, required=False, allow_blank=True)
    dimensions_text = serializers.CharField(max_length=120, required=False, allow_blank=True)
    year_text = serializers.CharField(max_length=40, required=False, allow_blank=True)
    expected_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=Decimal("1")
    )
    customer_notes = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    images = serializers.ListField(child=serializers.ImageField(), required=False, max_length=10)


class RequestTransitionSerializer(serializers.Serializer):
    to = serializers.ChoiceField(choices=RequestStatus.choices)
    message = serializers.CharField(required=False, allow_blank=True, default="")


class RequestNoteInputSerializer(serializers.Serializer):
    body = serializers.CharField()
    visibility = serializers.ChoiceField(choices=[("internal", "internal"), ("customer", "customer")])


class RequestArtworkInputSerializer(serializers.Serializer):
    category = serializers.SlugRelatedField(slug_field="slug", queryset=Category.objects.filter(is_active=True))


class CommissionInputSerializer(serializers.Serializer):
    rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, default="")

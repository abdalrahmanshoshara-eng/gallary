from __future__ import annotations

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuctionStaff, IsCustomer
from apps.artworks.models import Artwork
from apps.core import idempotency
from apps.core.errors import ConflictError

from .. import requests as request_services
from .. import selectors, services
from ..models import Auction, AuctionRequest, AuctionStatus, Bid, RequestStatus
from .serializers import (
    AdminAuctionRequestSerializer,
    AdminAuctionSerializer,
    AuctionCardSerializer,
    AuctionCreateSerializer,
    AuctionDetailSerializer,
    AuctionReasonSerializer,
    AuctionRequestInputSerializer,
    AuctionRequestSerializer,
    AuctionStateSerializer,
    AuctionWriteSerializer,
    BidInputSerializer,
    BidResultSerializer,
    CommissionInputSerializer,
    EligibleArtworkSerializer,
    MyBidAuctionSerializer,
    RequestArtworkInputSerializer,
    RequestNoteInputSerializer,
    RequestTransitionSerializer,
)

IDEMPOTENCY_HEADER = OpenApiParameter(
    "Idempotency-Key", str, location=OpenApiParameter.HEADER, required=True, description="UUID per bid attempt"
)


def _public(public_id) -> Auction:
    try:
        auction = selectors.public_auction(public_id)
    except Auction.DoesNotExist:
        raise ConflictError("المزاد غير موجود.", code="NOT_FOUND", http_status=404) from None
    seen = auction.version
    services.refresh(auction)  # lazy time transition: never render a stale state
    return selectors.public_auction(public_id) if auction.version != seen else auction


def _state(auction: Auction, user) -> dict:
    return AuctionStateSerializer(selectors.state(auction, user)).data


# --- public -------------------------------------------------------------------------------------------
class AuctionListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AuctionCardSerializer

    def get_queryset(self):
        return selectors.public_auctions(self.request.query_params.get("status", "live"))

    @extend_schema(
        operation_id="auctions_list",
        parameters=[OpenApiParameter("status", str, enum=["live", "upcoming", "ended"], default="live")],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class AuctionDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="auctions_detail", responses=AuctionDetailSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(AuctionDetailSerializer(_public(public_id)).data)


class AuctionStateView(APIView):
    """REST resync (ARCHITECTURE §5.4): after a reconnect or a `seq` gap."""

    permission_classes = [AllowAny]

    @extend_schema(operation_id="auctions_state", responses=AuctionStateSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(_state(_public(public_id), request.user))


class BidView(APIView):
    permission_classes = [IsCustomer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "bids"

    @extend_schema(
        operation_id="auctions_bid",
        request=BidInputSerializer,
        responses={201: BidResultSerializer, 200: BidResultSerializer},
        parameters=[IDEMPOTENCY_HEADER],
    )
    def post(self, request: Request, public_id) -> Response:
        key = idempotency.key_from(request)
        data = BidInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        auction = get_object_or_404(Auction.objects.filter(status__in=selectors.PUBLIC_STATUSES), public_id=public_id)
        result = services.place_bid(
            auction=auction,
            user=request.user,
            amount=data.validated_data["amount"],
            idempotency_key=key,
            ip=request.META.get("REMOTE_ADDR"),
        )
        fresh = selectors.public_auction(public_id)
        bid = result.bid
        body = {
            "bid": {"id": bid.public_id, "amount": bid.amount, "alias": bid.bidder_alias, "created_at": bid.created_at},
            "state": selectors.state(fresh, request.user),
            "replayed": result.replayed,
        }
        code = status.HTTP_200_OK if result.replayed else status.HTTP_201_CREATED
        return Response(BidResultSerializer(body).data, status=code)


class MyBidsView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="auctions_my_bids", responses=MyBidAuctionSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(MyBidAuctionSerializer(selectors.my_bid_auctions(request.user), many=True).data)


# --- customer auction requests (BR-601…607) ----------------------------------------------------------
def _request_qs():
    return AuctionRequest.objects.select_related("user", "resulting_auction", "resulting_artwork").prefetch_related(
        "images__asset", "notes__author", "history"
    )


def _my_request(request: Request, public_id) -> AuctionRequest:
    return get_object_or_404(_request_qs(), public_id=public_id, user=request.user)  # IDOR-safe


def _request_fields(validated: dict) -> dict:
    return {k: v for k, v in validated.items() if k != "images"}


class MyAuctionRequestsView(APIView):
    permission_classes = [IsCustomer]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(operation_id="auction_requests_mine", responses=AuctionRequestSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = _request_qs().filter(user=request.user)
        return Response(AuctionRequestSerializer(qs, many=True).data)

    @extend_schema(
        operation_id="auction_requests_submit",
        request={"multipart/form-data": AuctionRequestInputSerializer},
        responses={201: AuctionRequestSerializer},
    )
    def post(self, request: Request) -> Response:
        data = AuctionRequestInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = request_services.submit(
            user=request.user, data=_request_fields(data.validated_data), files=request.FILES.getlist("images")
        )
        return Response(AuctionRequestSerializer(_request_qs().get(pk=req.pk)).data, status=status.HTTP_201_CREATED)


class MyAuctionRequestView(APIView):
    permission_classes = [IsCustomer]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(operation_id="auction_requests_detail", responses=AuctionRequestSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(AuctionRequestSerializer(_my_request(request, public_id)).data)

    @extend_schema(
        operation_id="auction_requests_update",
        request={"multipart/form-data": AuctionRequestInputSerializer},
        responses=AuctionRequestSerializer,
    )
    def patch(self, request: Request, public_id) -> Response:
        req = _my_request(request, public_id)
        data = AuctionRequestInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        request_services.customer_update(
            req, user=request.user, data=_request_fields(data.validated_data), files=request.FILES.getlist("images")
        )
        return Response(AuctionRequestSerializer(_request_qs().get(pk=req.pk)).data)


class MyAuctionRequestWithdrawView(APIView):
    permission_classes = [IsCustomer]

    @extend_schema(operation_id="auction_requests_withdraw", request=None, responses=AuctionRequestSerializer)
    def post(self, request: Request, public_id) -> Response:
        req = _my_request(request, public_id)
        request_services.withdraw(req, user=request.user)
        return Response(AuctionRequestSerializer(_request_qs().get(pk=req.pk)).data)


# --- staff: auctions (BR-501…504, 517) ---------------------------------------------------------------
def _admin_qs():
    return Auction.objects.select_related(
        "listing__artwork__artist", "highest_bid", "current_winner_bid"
    ).prefetch_related("listing__artwork__images__asset")


def _admin_auction(public_id) -> Auction:
    auction = get_object_or_404(_admin_qs(), public_id=public_id)
    services.refresh(auction)
    return _admin_qs().get(pk=auction.pk)


def _admin_out(auction: Auction) -> dict:
    return AdminAuctionSerializer(_admin_qs().get(pk=auction.pk)).data


ADMIN_STATUS_FILTERS = ["active", *AuctionStatus.values]


class AdminAuctionListView(ListAPIView):
    permission_classes = [IsAuctionStaff]
    serializer_class = AuctionCardSerializer

    def get_queryset(self):
        p = self.request.query_params
        qs = selectors._with_cards(Auction.objects.all())
        state = p.get("status", "")
        if state == "active":  # needs attention: everything not final
            qs = qs.exclude(status__in=[AuctionStatus.ENDED, AuctionStatus.AWARDED, AuctionStatus.CANCELLED])
        elif state in AuctionStatus.values:
            qs = qs.filter(status=state)
        term = p.get("search", "").strip()
        if term:
            qs = qs.filter(Q(title__icontains=term) | Q(listing__artwork__title__icontains=term))
        if state in ("active", AuctionStatus.LIVE, AuctionStatus.SCHEDULED, AuctionStatus.PENDING_WINNER_PAYMENT):
            return qs.order_by("ends_at")  # most urgent first
        return qs.order_by("-created_at")

    @extend_schema(
        operation_id="admin_auctions_list",
        parameters=[OpenApiParameter("status", str, enum=ADMIN_STATUS_FILTERS), OpenApiParameter("search", str)],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="admin_auctions_create", request=AuctionCreateSerializer, responses={201: AdminAuctionSerializer}
    )
    def post(self, request: Request) -> Response:
        data = AuctionCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        artwork = get_object_or_404(Artwork, public_id=v.pop("artwork"))
        request_id = v.pop("request", None)
        commission = v.pop("commission_rate", None)
        source_request = None
        if request_id:
            source_request = get_object_or_404(AuctionRequest, public_id=request_id)
            if source_request.status != RequestStatus.APPROVED or source_request.resulting_auction_id:
                raise request_services.RequestStateError("الطلب غير جاهز لإنشاء مزاد.")
            if artwork.owner_user_id != source_request.user_id:
                raise ConflictError("العمل لا يخص مقدّم الطلب.", code="REQUEST_ARTWORK_MISMATCH")
            commission = source_request.agreed_commission_rate  # BR-606: the agreed share, not a new one
        auction = services.create_auction(
            actor=request.user,
            artwork=artwork,
            data=v,
            commission_rate_override=commission,
            source_request=source_request,
        )
        if source_request is not None:
            request_services.link_auction(source_request, auction=auction)
        return Response(_admin_out(auction), status=status.HTTP_201_CREATED)


class AdminAuctionDetailView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(operation_id="admin_auctions_detail", responses=AdminAuctionSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(AdminAuctionSerializer(_admin_auction(public_id)).data)

    @extend_schema(
        operation_id="admin_auctions_update", request=AuctionWriteSerializer, responses=AdminAuctionSerializer
    )
    def patch(self, request: Request, public_id) -> Response:
        auction = _admin_auction(public_id)
        data = AuctionWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        services.update_auction(auction, actor=request.user, data=data.validated_data)
        return Response(_admin_out(auction))


class AdminAuctionScheduleView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(operation_id="admin_auctions_schedule", request=None, responses=AdminAuctionSerializer)
    def post(self, request: Request, public_id) -> Response:
        auction = services.schedule(_admin_auction(public_id), actor=request.user)
        return Response(_admin_out(auction))


class AdminAuctionCancelView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(
        operation_id="admin_auctions_cancel", request=AuctionReasonSerializer, responses=AdminAuctionSerializer
    )
    def post(self, request: Request, public_id) -> Response:
        data = AuctionReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        auction = services.cancel(_admin_auction(public_id), actor=request.user, reason=data.validated_data["reason"])
        return Response(_admin_out(auction))


class AdminEligibleArtworksView(ListAPIView):
    """Artwork picker for a new auction: published, not archived, no live offer or open auction."""

    permission_classes = [IsAuctionStaff]
    serializer_class = EligibleArtworkSerializer

    def get_queryset(self):
        from apps.artworks.models import ArtworkImage, PublicationStatus
        from apps.listings.models import ListingStatus

        primary = ArtworkImage.objects.filter(is_primary=True).select_related("asset")
        busy_listing = Q(listings__status=ListingStatus.ACTIVE)
        open_auction = Q(
            listings__auction__status__in=[
                s for s in AuctionStatus.values if s not in ("ended", "awarded", "cancelled")
            ]
        )
        qs = (
            Artwork.objects.filter(publication_status=PublicationStatus.PUBLISHED, archived_at__isnull=True)
            .exclude(busy_listing | open_auction)
            .select_related("artist")
            .prefetch_related(Prefetch("images", queryset=primary, to_attr="primary_images"))
            .distinct()
            .order_by("-published_at")
        )
        term = self.request.query_params.get("search", "").strip()
        if term:
            qs = qs.filter(
                Q(title__icontains=term) | Q(artist__name__icontains=term) | Q(creator_name_override__icontains=term)
            )
        return qs

    @extend_schema(operation_id="admin_auctions_eligible_artworks", parameters=[OpenApiParameter("search", str)])
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class AdminBidVoidView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(
        operation_id="admin_auctions_void_bid", request=AuctionReasonSerializer, responses=AdminAuctionSerializer
    )
    def post(self, request: Request, public_id, bid_id) -> Response:
        data = AuctionReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        bid = get_object_or_404(Bid, public_id=bid_id, auction__public_id=public_id)
        auction = services.void_bid(bid, actor=request.user, reason=data.validated_data["reason"])
        return Response(_admin_out(auction))


# --- staff: auction requests --------------------------------------------------------------------------
def _admin_request(public_id) -> AuctionRequest:
    return get_object_or_404(_request_qs(), public_id=public_id)


def _admin_request_out(req: AuctionRequest) -> dict:
    return AdminAuctionRequestSerializer(_request_qs().get(pk=req.pk)).data


REQUEST_FILTERS = ["open", *RequestStatus.values]


class AdminAuctionRequestListView(ListAPIView):
    permission_classes = [IsAuctionStaff]
    serializer_class = AdminAuctionRequestSerializer

    def get_queryset(self):
        p = self.request.query_params
        qs = _request_qs()
        state = p.get("status", "open")
        if state == "open":
            qs = qs.exclude(status__in=[RequestStatus.REJECTED, RequestStatus.WITHDRAWN]).exclude(
                status=RequestStatus.APPROVED, resulting_auction__isnull=False
            )
        elif state in RequestStatus.values:
            qs = qs.filter(status=state)
        term = p.get("search", "").strip()
        if term:
            qs = qs.filter(
                Q(work_title__icontains=term)
                | Q(artist_name__icontains=term)
                | Q(contact_phone__icontains=term.lstrip("0"))
            )
        return qs.order_by("created_at") if state == "open" else qs.order_by("-created_at")  # oldest waiting first

    @extend_schema(
        operation_id="admin_auction_requests_list",
        parameters=[
            OpenApiParameter("status", str, enum=REQUEST_FILTERS, default="open"),
            OpenApiParameter("search", str),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class AdminAuctionRequestDetailView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(operation_id="admin_auction_requests_detail", responses=AdminAuctionRequestSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(AdminAuctionRequestSerializer(_admin_request(public_id)).data)


class AdminAuctionRequestTransitionView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(
        operation_id="admin_auction_requests_transition",
        request=RequestTransitionSerializer,
        responses=AdminAuctionRequestSerializer,
    )
    def post(self, request: Request, public_id) -> Response:
        data = RequestTransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = _admin_request(public_id)
        to, message = data.validated_data["to"], data.validated_data["message"]
        if to == RequestStatus.APPROVED:
            request_services.approve(req, actor=request.user, message=message)
        else:
            request_services.staff_transition(req, actor=request.user, to=to, message=message)
        return Response(_admin_request_out(req))


class AdminAuctionRequestNoteView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(
        operation_id="admin_auction_requests_note",
        request=RequestNoteInputSerializer,
        responses=AdminAuctionRequestSerializer,
    )
    def post(self, request: Request, public_id) -> Response:
        data = RequestNoteInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = _admin_request(public_id)
        request_services.add_note(req, actor=request.user, **data.validated_data)
        return Response(_admin_request_out(req))


class AdminAuctionRequestCommissionView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(
        operation_id="admin_auction_requests_commission",
        request=CommissionInputSerializer,
        responses=AdminAuctionRequestSerializer,
    )
    def post(self, request: Request, public_id) -> Response:
        data = CommissionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = _admin_request(public_id)
        request_services.set_commission(req, actor=request.user, **data.validated_data)
        return Response(_admin_request_out(req))


class AdminAuctionRequestArtworkView(APIView):
    permission_classes = [IsAuctionStaff]

    @extend_schema(
        operation_id="admin_auction_requests_create_artwork",
        request=RequestArtworkInputSerializer,
        responses={201: AdminAuctionRequestSerializer},
    )
    def post(self, request: Request, public_id) -> Response:
        data = RequestArtworkInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = _admin_request(public_id)
        request_services.create_artwork(req, actor=request.user, category=data.validated_data["category"])
        return Response(_admin_request_out(req), status=status.HTTP_201_CREATED)

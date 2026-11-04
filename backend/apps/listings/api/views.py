from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCatalogEditor, IsSuperAdmin
from apps.artworks import selectors as artwork_selectors
from apps.artworks.models import Artwork
from apps.audit import services as audit
from apps.core.http import client_ip
from apps.core.models import SiteSetting

from .. import selectors, services
from ..models import Listing, SaleMode
from .serializers import (
    AdminListingSerializer,
    ListingWriteSerializer,
    PricingSerializer,
    ReasonSerializer,
    SiteSettingSerializer,
    StorefrontCardSerializer,
    StorefrontDetailSerializer,
)


# --- public storefront ---------------------------------------------------------------------------
class StorefrontListView(ListAPIView):
    """Catalogue with Arabic-normalised search and filters (§21)."""

    permission_classes = [AllowAny]
    serializer_class = StorefrontCardSerializer

    def get_queryset(self):
        p = self.request.query_params
        return selectors.storefront_artworks(
            q=p.get("q", ""),
            category=p.get("category", ""),
            artist=p.get("artist", ""),
            materials=p.getlist("material"),
            techniques=p.getlist("technique"),
            price_min=p.get("price_min", ""),
            price_max=p.get("price_max", ""),
            availability=p.get("availability", ""),
            sale_mode=p.get("sale_mode", ""),
            ordering=p.get("ordering", "newest"),
        )

    @extend_schema(
        operation_id="artworks_list",
        parameters=[
            OpenApiParameter(
                "q", str, description="Search title, creator, description, category, materials, techniques"
            ),
            OpenApiParameter("category", str),
            OpenApiParameter("artist", str),
            OpenApiParameter("material", str, many=True),
            OpenApiParameter("technique", str, many=True),
            OpenApiParameter("price_min", str),
            OpenApiParameter("price_max", str),
            OpenApiParameter("availability", str, enum=["available", "unavailable"]),
            OpenApiParameter("sale_mode", str, enum=list(SaleMode.values)),
            OpenApiParameter("ordering", str, enum=list(selectors.ORDERINGS)),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class StorefrontDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="artworks_detail", responses=StorefrontDetailSerializer)
    def get(self, request: Request, slug: str) -> Response:
        artwork = get_object_or_404(selectors.with_offers(artwork_selectors.public_artwork_detail()), slug=slug)
        return Response(StorefrontDetailSerializer(artwork).data)


# --- staff -----------------------------------------------------------------------------------------
def _listing(public_id) -> Listing:
    return get_object_or_404(Listing.objects.select_related("artwork", "artwork__artist"), public_id=public_id)


def _out(listing: Listing) -> dict:
    listing = Listing.objects.select_related("artwork", "artwork__artist", "pricing_approved_by").get(pk=listing.pk)
    return AdminListingSerializer(listing, context={"settings": SiteSetting.load()}).data


class AdminArtworkListingsView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_artwork_listings", responses=AdminListingSerializer(many=True))
    def get(self, request: Request, public_id: str) -> Response:
        artwork = get_object_or_404(Artwork, public_id=public_id)
        listings = selectors.admin_listings_for(artwork).select_related("artwork", "artwork__artist")
        context = {"settings": SiteSetting.load()}
        return Response(AdminListingSerializer(listings, many=True, context=context).data)

    @extend_schema(
        operation_id="admin_artwork_listing_create",
        request=ListingWriteSerializer,
        responses={201: AdminListingSerializer},
    )
    def post(self, request: Request, public_id: str) -> Response:
        artwork = get_object_or_404(Artwork, public_id=public_id)
        data = ListingWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        listing = services.create_listing(actor=request.user, artwork=artwork, **data.validated_data)
        return Response(_out(listing), status=status.HTTP_201_CREATED)


class AdminListingDetailView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_listing_detail", responses=AdminListingSerializer)
    def get(self, request: Request, public_id: str) -> Response:
        return Response(_out(_listing(public_id)))

    @extend_schema(
        operation_id="admin_listing_update", request=ListingWriteSerializer, responses=AdminListingSerializer
    )
    def patch(self, request: Request, public_id: str) -> Response:
        data = ListingWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        listing = services.update_listing(_listing(public_id), actor=request.user, data=data.validated_data)
        return Response(_out(listing))

    @extend_schema(operation_id="admin_listing_delete", responses={204: None})
    def delete(self, request: Request, public_id: str) -> Response:
        services.delete_draft(_listing(public_id), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminListingPricingView(APIView):
    """BR-212: price, commission and deposit are the Super Admin's decision."""

    permission_classes = [IsSuperAdmin]

    @extend_schema(operation_id="admin_listing_pricing", request=PricingSerializer, responses=AdminListingSerializer)
    def post(self, request: Request, public_id: str) -> Response:
        data = PricingSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        listing = services.set_pricing(_listing(public_id), actor=request.user, **data.validated_data)
        return Response(_out(listing))


class AdminListingActivateView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_listing_activate", request=None, responses=AdminListingSerializer)
    def post(self, request: Request, public_id: str) -> Response:
        return Response(_out(services.activate(_listing(public_id), actor=request.user)))


class AdminListingWithdrawView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_listing_withdraw", request=ReasonSerializer, responses=AdminListingSerializer)
    def post(self, request: Request, public_id: str) -> Response:
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        listing = services.withdraw(_listing(public_id), actor=request.user, reason=data.validated_data["reason"])
        return Response(_out(listing))


class AdminSiteSettingView(APIView):
    """Staff can read the platform defaults; only the Super Admin changes them (BR-212)."""

    def get_permissions(self):
        return [IsCatalogEditor()] if self.request.method == "GET" else [IsSuperAdmin()]

    @extend_schema(operation_id="admin_settings", responses=SiteSettingSerializer)
    def get(self, request: Request) -> Response:
        return Response(SiteSettingSerializer(SiteSetting.load()).data)

    @extend_schema(operation_id="admin_settings_update", request=SiteSettingSerializer, responses=SiteSettingSerializer)
    def patch(self, request: Request) -> Response:
        with transaction.atomic():
            setting = SiteSetting.objects.select_for_update().get(pk=SiteSetting.load().pk)
            data = SiteSettingSerializer(setting, data=request.data, partial=True)
            data.is_valid(raise_exception=True)
            before = {k: str(getattr(setting, k)) for k in data.validated_data}
            data.save()
            changes = {
                k: {"from": before[k], "to": str(v)} for k, v in data.validated_data.items() if before[k] != str(v)
            }
            if changes:
                audit.record(
                    actor=request.user,
                    action="settings.updated",
                    entity=setting,
                    changes=changes,
                    ip=client_ip(request),
                )
        return Response(data.data)

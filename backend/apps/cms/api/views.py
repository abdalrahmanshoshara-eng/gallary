from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCatalogEditor
from apps.accounts.roles import is_super_admin
from apps.artworks.models import Artwork
from apps.core.errors import PermissionDeniedError
from apps.listings.api.serializers import StorefrontCardSerializer

from .. import selectors, services
from ..models import Banner, FaqItem, FeaturedArtwork, Page, PageSlug
from .serializers import (
    AdminBannerSerializer,
    AdminFaqSerializer,
    AdminFeaturedSerializer,
    AdminPageSerializer,
    BannerInputSerializer,
    FeaturedInputSerializer,
    MoveSerializer,
    PageDraftSerializer,
    PageLinkSerializer,
    PageVersionSerializer,
    PublicBannerSerializer,
    PublicFaqSerializer,
    PublicPageSerializer,
)


# --- public -------------------------------------------------------------------------------------------
class PublicPagesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="pages_list", responses=PageLinkSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PageLinkSerializer(selectors.published_pages(), many=True).data)


class PublicPageView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="pages_detail", responses=PublicPageSerializer)
    def get(self, request: Request, slug: str) -> Response:
        page = get_object_or_404(selectors.published_pages(), slug=slug)
        return Response(PublicPageSerializer(page).data)


class PublicFaqView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(operation_id="faq_list", responses=PublicFaqSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(PublicFaqSerializer(selectors.public_faq(), many=True).data)


class HomeSerializer(serializers.Serializer):
    banners = PublicBannerSerializer(many=True)
    featured = StorefrontCardSerializer(many=True)


class HomeView(APIView):
    """Managed parts of the home page (F-CMS-04); other sections use their own endpoints."""

    permission_classes = [AllowAny]

    @extend_schema(operation_id="home", responses=HomeSerializer)
    def get(self, request: Request) -> Response:
        data = {"banners": selectors.live_banners(), "featured": selectors.public_featured_artworks()}
        return Response(HomeSerializer(data).data)


# --- staff: pages ----------------------------------------------------------------------------------------
def _page(request: Request, slug: str, *, editing: bool = False) -> Page:
    if slug not in PageSlug.values:
        raise Http404
    page = services.page(slug)
    if editing and slug == PageSlug.DEPOSIT_POLICY and not is_super_admin(request.user):
        raise PermissionDeniedError("سياسة العربون يعدّلها المدير العام وحده لأن العملاء يقرّون بإصدارها.")
    return page


def _page_out(request: Request, page: Page) -> dict:
    page = Page.objects.select_related("published__published_by", "draft_updated_by").get(pk=page.pk)
    return AdminPageSerializer(page, context={"request": request, "with_versions": True}).data


class AdminPagesView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_pages_list", responses=AdminPageSerializer(many=True))
    def get(self, request: Request) -> Response:
        pages = [services.page(slug) for slug in PageSlug.values]
        pages = Page.objects.filter(pk__in=[p.pk for p in pages]).select_related(
            "published__published_by", "draft_updated_by"
        )
        order = {slug: i for i, slug in enumerate(PageSlug.values)}
        rows = sorted(pages, key=lambda p: order[p.slug])
        return Response(AdminPageSerializer(rows, many=True, context={"request": request}).data)


class AdminPageView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_pages_detail", responses=AdminPageSerializer)
    def get(self, request: Request, slug: str) -> Response:
        return Response(_page_out(request, _page(request, slug)))

    @extend_schema(operation_id="admin_pages_save_draft", request=PageDraftSerializer, responses=AdminPageSerializer)
    def put(self, request: Request, slug: str) -> Response:
        page = _page(request, slug, editing=True)
        data = PageDraftSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.save_draft(page, actor=request.user, **data.validated_data)
        return Response(_page_out(request, page))


class AdminPagePublishView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_pages_publish", request=None, responses=AdminPageSerializer)
    def post(self, request: Request, slug: str) -> Response:
        page = _page(request, slug, editing=True)
        services.publish(page, actor=request.user)
        return Response(_page_out(request, page))


class AdminPageVersionView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_pages_version", responses=PageVersionSerializer)
    def get(self, request: Request, slug: str, number: int) -> Response:
        page = _page(request, slug)
        version = get_object_or_404(page.versions.select_related("published_by"), number=number)
        return Response(PageVersionSerializer(version).data)


# --- staff: FAQ ------------------------------------------------------------------------------------------
def _faq_list() -> list:
    return AdminFaqSerializer(FaqItem.objects.all(), many=True).data


class AdminFaqListView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_faq_list", responses=AdminFaqSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(_faq_list())

    @extend_schema(
        operation_id="admin_faq_create", request=AdminFaqSerializer, responses={201: AdminFaqSerializer(many=True)}
    )
    def post(self, request: Request) -> Response:
        data = AdminFaqSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.save_faq(None, actor=request.user, data=dict(data.validated_data))
        return Response(_faq_list(), status=status.HTTP_201_CREATED)


class AdminFaqItemView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_faq_update", request=AdminFaqSerializer, responses=AdminFaqSerializer(many=True))
    def patch(self, request: Request, public_id) -> Response:
        item = get_object_or_404(FaqItem, public_id=public_id)
        data = AdminFaqSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        services.save_faq(item, actor=request.user, data=dict(data.validated_data))
        return Response(_faq_list())

    @extend_schema(operation_id="admin_faq_delete", responses=AdminFaqSerializer(many=True))
    def delete(self, request: Request, public_id) -> Response:
        services.delete_faq(get_object_or_404(FaqItem, public_id=public_id), actor=request.user)
        return Response(_faq_list())


class AdminFaqMoveView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_faq_move", request=MoveSerializer, responses=AdminFaqSerializer(many=True))
    def post(self, request: Request, public_id) -> Response:
        data = MoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.move_faq(get_object_or_404(FaqItem, public_id=public_id), data.validated_data["direction"])
        return Response(_faq_list())


# --- staff: banners ---------------------------------------------------------------------------------------
def _banner_values(request: Request, data) -> dict:
    values = dict(data.validated_data)
    # HTML-form semantics turn an absent checkbox into False: only honour it when sent.
    if "is_active" not in request.data:
        values.pop("is_active", None)
    return values


def _banners() -> list:
    return AdminBannerSerializer(Banner.objects.select_related("image"), many=True).data


class AdminBannerListView(APIView):
    permission_classes = [IsCatalogEditor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(operation_id="admin_banners_list", responses=AdminBannerSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(_banners())

    @extend_schema(
        operation_id="admin_banners_create",
        request={"multipart/form-data": BannerInputSerializer},
        responses={201: AdminBannerSerializer(many=True)},
    )
    def post(self, request: Request) -> Response:
        data = BannerInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = _banner_values(request, data)
        image = values.pop("image", None)
        services.save_banner(None, actor=request.user, data=values, image=image)
        return Response(_banners(), status=status.HTTP_201_CREATED)


class AdminBannerView(APIView):
    permission_classes = [IsCatalogEditor]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        operation_id="admin_banners_update",
        request={"multipart/form-data": BannerInputSerializer},
        responses=AdminBannerSerializer(many=True),
    )
    def patch(self, request: Request, public_id) -> Response:
        banner = get_object_or_404(Banner, public_id=public_id)
        data = BannerInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = _banner_values(request, data)
        image = values.pop("image", None)
        services.save_banner(banner, actor=request.user, data=values, image=image)
        return Response(_banners())

    @extend_schema(operation_id="admin_banners_delete", responses=AdminBannerSerializer(many=True))
    def delete(self, request: Request, public_id) -> Response:
        services.delete_banner(get_object_or_404(Banner, public_id=public_id), actor=request.user)
        return Response(_banners())


class AdminBannerMoveView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(
        operation_id="admin_banners_move", request=MoveSerializer, responses=AdminBannerSerializer(many=True)
    )
    def post(self, request: Request, public_id) -> Response:
        data = MoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.move_banner(get_object_or_404(Banner, public_id=public_id), data.validated_data["direction"])
        return Response(_banners())


# --- staff: featured artworks ----------------------------------------------------------------------------
def _featured() -> list:
    return AdminFeaturedSerializer(selectors.featured_items(), many=True).data


class AdminFeaturedListView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_featured_list", responses=AdminFeaturedSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(_featured())

    @extend_schema(
        operation_id="admin_featured_add",
        request=FeaturedInputSerializer,
        responses={201: AdminFeaturedSerializer(many=True)},
    )
    def post(self, request: Request) -> Response:
        data = FeaturedInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        artwork = get_object_or_404(Artwork, public_id=data.validated_data["artwork"])
        services.add_featured(artwork, actor=request.user)
        return Response(_featured(), status=status.HTTP_201_CREATED)


class AdminFeaturedItemView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_featured_remove", responses=AdminFeaturedSerializer(many=True))
    def delete(self, request: Request, artwork_id) -> Response:
        item = get_object_or_404(FeaturedArtwork, artwork__public_id=artwork_id)
        services.remove_featured(item, actor=request.user)
        return Response(_featured())


class AdminFeaturedMoveView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(
        operation_id="admin_featured_move", request=MoveSerializer, responses=AdminFeaturedSerializer(many=True)
    )
    def post(self, request: Request, artwork_id) -> Response:
        data = MoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = get_object_or_404(FeaturedArtwork, artwork__public_id=artwork_id)
        services.move_featured(item, data.validated_data["direction"])
        return Response(_featured())

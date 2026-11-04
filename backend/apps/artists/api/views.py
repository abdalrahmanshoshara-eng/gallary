from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCatalogEditor

from .. import selectors, services
from ..models import Artist
from .serializers import AdminArtistSerializer, ImageUploadSerializer, PublicArtistSerializer


class PublicArtistListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicArtistSerializer

    def get_queryset(self):
        qs = selectors.public_artists()
        if self.request.query_params.get("featured") == "true":
            qs = qs.filter(is_featured=True)
        return qs

    @extend_schema(
        operation_id="artists_list", parameters=[OpenApiParameter("featured", bool, description="المميزون فقط")]
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class PublicArtistDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicArtistSerializer
    lookup_field = "slug"
    lookup_url_kwarg = "slug"

    def get_queryset(self):
        return selectors.public_artists()

    @extend_schema(operation_id="artists_detail")
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class AdminArtistListView(ListAPIView):
    permission_classes = [IsCatalogEditor]
    serializer_class = AdminArtistSerializer

    def get_queryset(self):
        p = self.request.query_params
        return selectors.admin_artists(search=p.get("search", ""), status=p.get("status", ""))

    @extend_schema(
        operation_id="admin_artists_list",
        parameters=[OpenApiParameter("search", str), OpenApiParameter("status", str, enum=["active", "hidden"])],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="admin_artists_create", request=AdminArtistSerializer, responses={201: AdminArtistSerializer}
    )
    def post(self, request: Request) -> Response:
        data = AdminArtistSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        artist = services.create_artist(actor=request.user, data=dict(data.validated_data))
        return Response(
            AdminArtistSerializer(selectors.admin_artists().get(pk=artist.pk)).data, status=status.HTTP_201_CREATED
        )


class AdminArtistDetailView(APIView):
    permission_classes = [IsCatalogEditor]

    def _get(self, public_id) -> Artist:
        return get_object_or_404(selectors.admin_artists(), public_id=public_id)

    @extend_schema(operation_id="admin_artists_get", responses=AdminArtistSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(AdminArtistSerializer(self._get(public_id)).data)

    @extend_schema(operation_id="admin_artists_update", request=AdminArtistSerializer, responses=AdminArtistSerializer)
    def patch(self, request: Request, public_id) -> Response:
        artist = self._get(public_id)
        data = AdminArtistSerializer(artist, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if values.get("slug") == "":
            values.pop("slug")
        services.update_artist(artist, actor=request.user, data=values)
        return Response(AdminArtistSerializer(self._get(public_id)).data)

    @extend_schema(operation_id="admin_artists_delete", responses={204: None})
    def delete(self, request: Request, public_id) -> Response:
        services.delete_artist(self._get(public_id), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminArtistPhotoView(APIView):
    permission_classes = [IsCatalogEditor]
    parser_classes = [MultiPartParser]

    @extend_schema(
        operation_id="admin_artists_photo_upload",
        request={"multipart/form-data": ImageUploadSerializer},
        responses=AdminArtistSerializer,
    )
    def post(self, request: Request, public_id) -> Response:
        artist = get_object_or_404(Artist, public_id=public_id)
        data = ImageUploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_photo(artist, data.validated_data["file"], actor=request.user)
        return Response(AdminArtistSerializer(selectors.admin_artists().get(pk=artist.pk)).data)

    @extend_schema(operation_id="admin_artists_photo_delete", responses=AdminArtistSerializer)
    def delete(self, request: Request, public_id) -> Response:
        artist = get_object_or_404(Artist, public_id=public_id)
        services.remove_photo(artist, actor=request.user)
        return Response(AdminArtistSerializer(selectors.admin_artists().get(pk=artist.pk)).data)

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCatalogEditor
from apps.artists.api.serializers import ImageUploadSerializer

from .. import selectors, services
from ..models import Artwork, ArtworkImage
from .serializers import (
    AdminArtworkImageSerializer,
    AdminArtworkListSerializer,
    AdminArtworkSerializer,
    ArchiveInputSerializer,
    HideInputSerializer,
    ImageOrderSerializer,
    ImageUpdateSerializer,
    PublicArtworkCardSerializer,
)


class PublicArchiveListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicArtworkCardSerializer

    def get_queryset(self):
        return selectors.archive_artworks(artist=self.request.query_params.get("artist", ""))

    @extend_schema(operation_id="archive_list", parameters=[OpenApiParameter("artist", str)])
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


# --- staff ------------------------------------------------------------------------------------
def _detail(public_id) -> Artwork:
    return get_object_or_404(selectors.admin_artwork_detail(), public_id=public_id)


class AdminArtworkListView(ListAPIView):
    permission_classes = [IsCatalogEditor]
    serializer_class = AdminArtworkListSerializer

    def get_queryset(self):
        p = self.request.query_params
        return selectors.admin_artworks(
            search=p.get("search", ""),
            status=p.get("status", ""),
            category=p.get("category", ""),
            artist=p.get("artist", ""),
            archived=p.get("archived", ""),
        )

    @extend_schema(
        operation_id="admin_artworks_list",
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("status", str, enum=["draft", "published", "hidden"]),
            OpenApiParameter("category", str),
            OpenApiParameter("artist", str, description="public id"),
            OpenApiParameter("archived", str, enum=["true", "false"]),
        ],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="admin_artworks_create", request=AdminArtworkSerializer, responses={201: AdminArtworkSerializer}
    )
    def post(self, request: Request) -> Response:
        data = AdminArtworkSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        artwork = services.create_artwork(actor=request.user, data=dict(data.validated_data))
        return Response(AdminArtworkSerializer(_detail(artwork.public_id)).data, status=status.HTTP_201_CREATED)


class AdminArtworkDetailView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(operation_id="admin_artworks_get", responses=AdminArtworkSerializer)
    def get(self, request: Request, public_id) -> Response:
        return Response(AdminArtworkSerializer(_detail(public_id)).data)

    @extend_schema(
        operation_id="admin_artworks_update", request=AdminArtworkSerializer, responses=AdminArtworkSerializer
    )
    def patch(self, request: Request, public_id) -> Response:
        artwork = _detail(public_id)
        data = AdminArtworkSerializer(artwork, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if values.get("slug") == "":
            values.pop("slug")
        services.update_artwork(artwork, actor=request.user, data=values)
        return Response(AdminArtworkSerializer(_detail(public_id)).data)

    @extend_schema(operation_id="admin_artworks_delete", responses={204: None})
    def delete(self, request: Request, public_id) -> Response:
        services.delete_artwork(get_object_or_404(Artwork, public_id=public_id), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _action_view(name: str, handler, input_serializer=None):
    class View(APIView):
        permission_classes = [IsCatalogEditor]

        @extend_schema(
            operation_id=f"admin_artworks_{name}", request=input_serializer, responses=AdminArtworkSerializer
        )
        def post(self, request: Request, public_id) -> Response:
            artwork = get_object_or_404(Artwork, public_id=public_id)
            kwargs = {}
            if input_serializer is not None:
                data = input_serializer(data=request.data)
                data.is_valid(raise_exception=True)
                kwargs = dict(data.validated_data)
            handler(artwork, actor=request.user, **kwargs)
            return Response(AdminArtworkSerializer(_detail(public_id)).data)

    View.__name__ = f"AdminArtwork{name.title()}View"
    return View


AdminArtworkPublishView = _action_view("publish", services.publish)
AdminArtworkHideView = _action_view("hide", services.hide, HideInputSerializer)
AdminArtworkArchiveView = _action_view("archive", services.archive, ArchiveInputSerializer)
AdminArtworkUnarchiveView = _action_view("unarchive", services.unarchive)


class AdminArtworkImagesView(APIView):
    permission_classes = [IsCatalogEditor]
    parser_classes = [MultiPartParser]

    @extend_schema(
        operation_id="admin_artworks_images_upload",
        request={"multipart/form-data": ImageUploadSerializer},
        responses={201: AdminArtworkImageSerializer},
    )
    def post(self, request: Request, public_id) -> Response:
        artwork = get_object_or_404(Artwork, public_id=public_id)
        data = ImageUploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        image = services.add_image(
            artwork, data.validated_data["file"], actor=request.user, alt_text=data.validated_data["alt_text"]
        )
        return Response(AdminArtworkImageSerializer(image).data, status=status.HTTP_201_CREATED)


class AdminArtworkImageOrderView(APIView):
    permission_classes = [IsCatalogEditor]

    @extend_schema(
        operation_id="admin_artworks_images_reorder", request=ImageOrderSerializer, responses=AdminArtworkSerializer
    )
    def put(self, request: Request, public_id) -> Response:
        artwork = get_object_or_404(Artwork, public_id=public_id)
        data = ImageOrderSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.reorder_images(artwork, data.validated_data["ids"], actor=request.user)
        return Response(AdminArtworkSerializer(_detail(public_id)).data)


class AdminArtworkImageDetailView(APIView):
    permission_classes = [IsCatalogEditor]

    def _image(self, public_id, image_id) -> ArtworkImage:
        return get_object_or_404(
            ArtworkImage.objects.select_related("artwork", "asset"), public_id=image_id, artwork__public_id=public_id
        )

    @extend_schema(
        operation_id="admin_artworks_images_update", request=ImageUpdateSerializer, responses=AdminArtworkSerializer
    )
    def patch(self, request: Request, public_id, image_id) -> Response:
        image = self._image(public_id, image_id)
        data = ImageUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update_image(
            image,
            actor=request.user,
            alt_text=data.validated_data.get("alt_text"),
            make_primary=data.validated_data.get("is_primary", False),
        )
        return Response(AdminArtworkSerializer(_detail(public_id)).data)

    @extend_schema(operation_id="admin_artworks_images_delete", responses=AdminArtworkSerializer)
    def delete(self, request: Request, public_id, image_id) -> Response:
        services.delete_image(self._image(public_id, image_id), actor=request.user)
        return Response(AdminArtworkSerializer(_detail(public_id)).data)

"""
A user's favourite artworks. Only works the public can see can be added, and the list only
shows works that are still visible, so a hidden work quietly disappears from it.
"""

from __future__ import annotations

from django.db.models import Max
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artworks import selectors as artwork_selectors
from apps.artworks.models import Artwork
from apps.listings.api.serializers import StorefrontCardSerializer
from apps.listings.selectors import with_offers

from .. import services
from ..models import Favorite


def _visible_artworks():
    return Artwork.objects.filter(artwork_selectors.public_artwork_filter())


class FavoriteIdsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField())


class FavoriteListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StorefrontCardSerializer

    def get_queryset(self):
        qs = artwork_selectors.public_artwork_detail().filter(favorited_by__user=self.request.user)
        qs = qs.annotate(favorited_at=Max("favorited_by__created_at"))
        return with_offers(qs).select_related("category").order_by("-favorited_at", "-id")

    @extend_schema(operation_id="favorites_list")
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class FavoriteIdsView(APIView):
    """Lets cached public pages mark hearts client-side without personalising the page."""

    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="favorites_ids", responses=FavoriteIdsSerializer)
    def get(self, request: Request) -> Response:
        ids = Favorite.objects.filter(user=request.user, artwork__in=_visible_artworks()).values_list(
            "artwork__public_id", flat=True
        )
        return Response({"ids": list(ids)})


class FavoriteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="favorites_add", request=None, responses={201: None, 204: None})
    def put(self, request: Request, artwork_id: str) -> Response:
        artwork = get_object_or_404(_visible_artworks(), public_id=artwork_id)
        created = services.add(request.user, artwork)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_204_NO_CONTENT)

    @extend_schema(operation_id="favorites_remove", responses={204: None})
    def delete(self, request: Request, artwork_id: str) -> Response:
        # Removal works even if the work is no longer public (no existence oracle needed).
        artwork = Artwork.objects.filter(public_id=artwork_id).first()
        if artwork is not None:
            services.remove(request.user, artwork)
        return Response(status=status.HTTP_204_NO_CONTENT)

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import ImageAsset
from .storage import public_storage


class ImageVariantSerializer(serializers.Serializer):
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    url = serializers.URLField()


class PublicImageSerializer(serializers.Serializer):
    """Responsive image for the frontend: variants are listed by ascending width (srcset)."""

    id = serializers.UUIDField(source="public_id")
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    variants = serializers.SerializerMethodField()

    @extend_schema_field(ImageVariantSerializer(many=True))
    def get_variants(self, asset: ImageAsset) -> list[dict]:
        storage = public_storage()
        items = sorted(asset.variants.values(), key=lambda v: v["width"])
        return [{"width": v["width"], "height": v["height"], "url": storage.url(v["key"])} for v in items]


class AdminImageSerializer(PublicImageSerializer):
    status = serializers.CharField()
    error = serializers.CharField()

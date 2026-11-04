from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.media.serializers import AdminImageSerializer, PublicImageSerializer

from ..models import Artist


class ArtistRefSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


class PublicArtistSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    photo = serializers.SerializerMethodField()
    artwork_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Artist
        fields = ["id", "name", "slug", "biography", "city", "birth_year", "is_featured", "photo", "artwork_count"]
        read_only_fields = fields

    @extend_schema_field(PublicImageSerializer(allow_null=True))
    def get_photo(self, artist: Artist):
        photo = artist.photo
        return PublicImageSerializer(photo).data if photo is not None and photo.is_ready else None


class AdminArtistSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    photo = AdminImageSerializer(read_only=True, allow_null=True)
    artwork_count = serializers.IntegerField(read_only=True, default=0)
    slug = serializers.SlugField(allow_unicode=True, required=False, allow_blank=True, max_length=220)
    contact_email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = Artist
        fields = [
            "id",
            "name",
            "slug",
            "biography",
            "city",
            "birth_year",
            "status",
            "is_featured",
            "contact_phone",
            "contact_email",
            "internal_notes",
            "photo",
            "artwork_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_slug(self, value: str) -> str:
        if value and Artist.objects.filter(slug=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("هذا المعرّف مستخدم.")
        return value


class ImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    alt_text = serializers.CharField(max_length=250, required=False, allow_blank=True, default="")

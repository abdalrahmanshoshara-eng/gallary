from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artists.api.serializers import ArtistRefSerializer
from apps.artists.models import Artist
from apps.catalog.api.serializers import TermRefSerializer
from apps.catalog.models import Category, Material, Tag, Technique
from apps.media.serializers import AdminImageSerializer, PublicImageSerializer

from ..models import ArchiveVisibility, Artwork, ArtworkImage


class PublicArtworkImageSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    alt_text = serializers.CharField()
    image = PublicImageSerializer(source="asset")


def _primary(artwork: Artwork):
    images = getattr(artwork, "primary_images", None)
    if images is None:
        images = [i for i in artwork.images.all() if i.is_primary]
    image = images[0] if images else None
    if image is None or not image.asset.is_ready:
        return None
    return {"id": image.public_id, "alt_text": image.alt_text, "image": PublicImageSerializer(image.asset).data}


class DimensionsSerializer(serializers.Serializer):
    height_cm = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    width_cm = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    depth_cm = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    weight_kg = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)


class PublicArtworkCardSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    artist = ArtistRefSerializer(allow_null=True)
    creator_name = serializers.CharField(source="creator_display")
    category = TermRefSerializer()
    primary_image = serializers.SerializerMethodField()
    is_archived = serializers.BooleanField()

    class Meta:
        model = Artwork
        fields = [
            "id",
            "slug",
            "title",
            "artist",
            "creator_name",
            "category",
            "year_created",
            "primary_image",
            "is_archived",
        ]
        read_only_fields = fields

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_primary_image(self, artwork: Artwork):
        return _primary(artwork)


class CategoryWithParentSerializer(TermRefSerializer):
    parent = TermRefSerializer(allow_null=True)


class PublicArtworkDetailSerializer(PublicArtworkCardSerializer):
    executor = ArtistRefSerializer(allow_null=True)
    owner_name = serializers.CharField()
    rights_holder = serializers.CharField()
    category = CategoryWithParentSerializer()
    materials = TermRefSerializer(many=True)
    techniques = TermRefSerializer(many=True)
    tags = TermRefSerializer(many=True)
    dimensions = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField()

    class Meta(PublicArtworkCardSerializer.Meta):
        fields = [
            *PublicArtworkCardSerializer.Meta.fields,
            "description",
            "executor",
            "owner_name",
            "rights_holder",
            "materials",
            "techniques",
            "tags",
            "dimensions",
            "images",
            "published_at",
        ]
        read_only_fields = fields

    @extend_schema_field(DimensionsSerializer)
    def get_dimensions(self, artwork: Artwork):
        return DimensionsSerializer(artwork).data

    @extend_schema_field(PublicArtworkImageSerializer(many=True))
    def get_images(self, artwork: Artwork):
        images = getattr(artwork, "ready_images", None)
        if images is None:
            images = [i for i in artwork.images.all() if i.asset.is_ready]
        primary = [i for i in images if i.is_primary]
        rest = [i for i in images if not i.is_primary]
        return PublicArtworkImageSerializer(primary + rest, many=True).data


# --- staff ------------------------------------------------------------------------------------
class AdminArtworkImageSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    image = AdminImageSerializer(source="asset", read_only=True)

    class Meta:
        model = ArtworkImage
        fields = ["id", "alt_text", "sort_order", "is_primary", "image"]


class AdminArtworkListSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    artist = ArtistRefSerializer(allow_null=True)
    creator_name = serializers.CharField(source="creator_display")
    category = TermRefSerializer()
    primary_image = serializers.SerializerMethodField()
    is_archived = serializers.BooleanField()

    class Meta:
        model = Artwork
        fields = [
            "id",
            "slug",
            "title",
            "artist",
            "creator_name",
            "category",
            "publication_status",
            "is_archived",
            "archive_visibility",
            "published_at",
            "updated_at",
            "primary_image",
        ]

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_primary_image(self, artwork: Artwork):
        return _primary(artwork)


class AdminArtworkSerializer(serializers.ModelSerializer):
    """Read + write. Relations are written by id (category, terms) or public id (artists)."""

    id = serializers.UUIDField(source="public_id", read_only=True)
    slug = serializers.SlugField(allow_unicode=True, required=False, allow_blank=True, max_length=270)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    artist = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Artist.objects.all(), allow_null=True, required=False
    )
    executor = serializers.SlugRelatedField(
        slug_field="public_id", queryset=Artist.objects.all(), allow_null=True, required=False
    )
    materials = serializers.PrimaryKeyRelatedField(queryset=Material.objects.all(), many=True, required=False)
    techniques = serializers.PrimaryKeyRelatedField(queryset=Technique.objects.all(), many=True, required=False)
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)
    images = AdminArtworkImageSerializer(many=True, read_only=True)
    is_archived = serializers.BooleanField(read_only=True)
    owner_user_phone = serializers.CharField(source="owner_user.phone", read_only=True, allow_null=True, default=None)
    publish_problems = serializers.SerializerMethodField()

    class Meta:
        model = Artwork
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "artist",
            "creator_name_override",
            "executor",
            "owner_name",
            "owner_user_phone",
            "rights_holder",
            "materials",
            "techniques",
            "tags",
            "height_cm",
            "width_cm",
            "depth_cm",
            "weight_kg",
            "year_created",
            "internal_notes",
            "publication_status",
            "published_at",
            "is_archived",
            "archived_at",
            "archive_visibility",
            "images",
            "publish_problems",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "publication_status",
            "published_at",
            "archived_at",
            "archive_visibility",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_publish_problems(self, artwork: Artwork) -> list[str]:
        from ..services import publish_problems

        return publish_problems(artwork)

    def validate_slug(self, value: str) -> str:
        if value and Artwork.objects.filter(slug=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("هذا المعرّف مستخدم.")
        return value

    def validate(self, attrs):
        artist = attrs.get("artist", getattr(self.instance, "artist", None))
        creator = attrs.get("creator_name_override", getattr(self.instance, "creator_name_override", ""))
        if artist is None and not (creator or "").strip():
            raise serializers.ValidationError({"artist": ["اختر الفنان أو اكتب اسم المُبدع."]})
        category = attrs.get("category")
        if (
            category is not None
            and not category.is_active
            and getattr(self.instance, "category_id", None) != category.pk
        ):
            raise serializers.ValidationError({"category": ["هذا التصنيف معطّل."]})
        return attrs


class ArchiveInputSerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(choices=ArchiveVisibility.choices, default=ArchiveVisibility.VISIBLE)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class HideInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ImageOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class ImageUpdateSerializer(serializers.Serializer):
    alt_text = serializers.CharField(max_length=250, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False)

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..models import Category, Material, Tag, Technique


class TermRefSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


class PublicCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["name", "slug", "description", "children"]
        read_only_fields = fields

    @extend_schema_field(TermRefSerializer(many=True))
    def get_children(self, obj: Category) -> list[dict]:
        return [{"name": c.name, "slug": c.slug} for c in obj.children.all()]


class PublicTermSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()


_TERM_FIELDS = ["id", "name", "slug", "is_active", "sort_order", "usage_count"]


class _AdminTermSerializer(serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True, default=0)
    slug = serializers.SlugField(allow_unicode=True, required=False, allow_blank=True, max_length=120)

    def validate_slug(self, value: str) -> str:
        if not value:
            return value
        qs = self.Meta.model.objects.filter(slug=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("هذا المعرّف مستخدم.")
        return value


class AdminCategorySerializer(_AdminTermSerializer):
    parent = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Category
        fields = [*_TERM_FIELDS, "parent", "description"]


class AdminMaterialSerializer(_AdminTermSerializer):
    class Meta:
        model = Material
        fields = _TERM_FIELDS


class AdminTechniqueSerializer(_AdminTermSerializer):
    class Meta:
        model = Technique
        fields = _TERM_FIELDS


class AdminTagSerializer(_AdminTermSerializer):
    class Meta:
        model = Tag
        fields = _TERM_FIELDS

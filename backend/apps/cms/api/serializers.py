from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artworks.api.serializers import PublicArtworkImageSerializer, _primary
from apps.media.serializers import AdminImageSerializer, PublicImageSerializer

from .. import services
from ..models import Banner, FaqItem, FeaturedArtwork, Page, PageSlug, PageVersion

MARKDOWN_HELP = "Limited Markdown: paragraphs, ## / ### headings, - and 1. lists, **bold**, [text](url)."


# --- public -------------------------------------------------------------------------------------------
class PublicPageSerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField(source="published.title")
    body = serializers.CharField(source="published.body", help_text=MARKDOWN_HELP)
    version = serializers.IntegerField(source="published.number")
    code = serializers.CharField(source="published.code")
    published_at = serializers.DateTimeField(source="published.published_at")


class PageLinkSerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField(source="published.title")


class PublicFaqSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    question = serializers.CharField()
    answer = serializers.CharField(help_text=MARKDOWN_HELP)


class PublicBannerSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    title = serializers.CharField()
    subtitle = serializers.CharField()
    image = PublicImageSerializer()
    link_url = serializers.CharField()
    link_label = serializers.CharField()


# --- staff: pages ---------------------------------------------------------------------------------------
class PageVersionSerializer(serializers.ModelSerializer):
    published_by = serializers.CharField(source="published_by.display_name", allow_null=True, default=None)

    class Meta:
        model = PageVersion
        fields = ["number", "code", "title", "body", "published_at", "published_by"]
        read_only_fields = fields


class PageVersionSummarySerializer(PageVersionSerializer):
    class Meta(PageVersionSerializer.Meta):
        fields = ["number", "code", "title", "published_at", "published_by"]
        read_only_fields = fields


class AdminPageSerializer(serializers.Serializer):
    slug = serializers.ChoiceField(choices=PageSlug.choices)
    label = serializers.SerializerMethodField()
    draft_title = serializers.CharField()
    draft_body = serializers.CharField()
    draft_updated_at = serializers.DateTimeField(allow_null=True)
    draft_updated_by = serializers.CharField(source="draft_updated_by.display_name", allow_null=True, default=None)
    published = PageVersionSerializer(allow_null=True)
    unpublished_changes = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField(help_text="The deposit policy is the Super Admin's only")
    versions = serializers.SerializerMethodField()

    def get_label(self, page: Page) -> str:
        return PageSlug(page.slug).label

    def get_unpublished_changes(self, page: Page) -> bool:
        return services.has_unpublished_changes(page)

    def get_can_edit(self, page: Page) -> bool:
        from apps.accounts.roles import is_super_admin

        return page.slug != PageSlug.DEPOSIT_POLICY or is_super_admin(self.context["request"].user)

    @extend_schema_field(PageVersionSummarySerializer(many=True))
    def get_versions(self, page: Page):
        if not self.context.get("with_versions"):
            return []
        return PageVersionSummarySerializer(page.versions.select_related("published_by"), many=True).data


class PageDraftSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=True)
    body = serializers.CharField(allow_blank=True, max_length=60000, help_text=MARKDOWN_HELP)


# --- staff: FAQ, banners, featured ---------------------------------------------------------------------
class AdminFaqSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = FaqItem
        fields = ["id", "question", "answer", "is_active", "sort_order", "updated_at"]
        read_only_fields = ["id", "sort_order", "updated_at"]
        extra_kwargs = {"question": {"required": False}, "answer": {"required": False}}


class MoveSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=["up", "down"])


class AdminBannerSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    image = AdminImageSerializer(read_only=True, allow_null=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "image",
            "link_url",
            "link_label",
            "is_active",
            "starts_at",
            "ends_at",
            "sort_order",
            "state",
        ]
        read_only_fields = ["id", "image", "sort_order", "state"]

    @extend_schema_field(serializers.ChoiceField(choices=["live", "scheduled", "expired", "hidden"]))
    def get_state(self, banner: Banner) -> str:
        return services.banner_state(banner)


class BannerInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, required=False)
    subtitle = serializers.CharField(max_length=300, required=False, allow_blank=True)
    link_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    link_label = serializers.CharField(max_length=60, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    image = serializers.ImageField(required=False)


class AdminFeaturedSerializer(serializers.Serializer):
    artwork_id = serializers.UUIDField(source="artwork.public_id")
    title = serializers.CharField(source="artwork.title")
    creator_name = serializers.CharField(source="artwork.creator_display")
    image = serializers.SerializerMethodField()
    is_public = serializers.SerializerMethodField(help_text="False when the work was hidden or archived (not shown)")
    sort_order = serializers.IntegerField()

    @extend_schema_field(PublicArtworkImageSerializer(allow_null=True))
    def get_image(self, item: FeaturedArtwork):
        return _primary(item.artwork)

    def get_is_public(self, item: FeaturedArtwork) -> bool:
        return item.artwork.publication_status == "published" and item.artwork.archived_at is None


class FeaturedInputSerializer(serializers.Serializer):
    artwork = serializers.UUIDField()

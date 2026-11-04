from django.contrib import admin

from .models import Artwork, ArtworkImage


class ArtworkImageInline(admin.TabularInline):
    model = ArtworkImage
    extra = 0
    readonly_fields = ("asset",)


@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    list_display = ("title", "artist", "category", "publication_status", "archived_at", "published_at")
    list_filter = ("publication_status", "category")
    search_fields = ("title", "artist__name", "creator_name_override")
    readonly_fields = ("public_id", "published_at", "archived_at", "created_by", "created_at", "updated_at")
    inlines = [ArtworkImageInline]

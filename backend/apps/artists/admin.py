from django.contrib import admin

from .models import Artist


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "is_featured", "created_at")
    list_filter = ("status", "is_featured")
    search_fields = ("name", "contact_phone", "contact_email")
    readonly_fields = ("public_id", "photo", "created_by", "created_at", "updated_at")

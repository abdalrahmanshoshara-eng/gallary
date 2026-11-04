from django.contrib import admin

from .models import ImageAsset


@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ("public_id", "purpose", "status", "width", "height", "created_at")
    list_filter = ("purpose", "status")
    readonly_fields = [f.name for f in ImageAsset._meta.fields]

    def has_add_permission(self, request):
        return False

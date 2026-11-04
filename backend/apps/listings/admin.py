from django.contrib import admin

from .models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """Read-only helper view; changes go through the API so rules and audit apply."""

    list_display = ["artwork", "status", "sale_mode", "price_usd", "quantity_mode", "quantity_available"]
    list_filter = ["status", "sale_mode", "quantity_mode"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

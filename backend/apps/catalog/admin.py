from django.contrib import admin

from .models import Category, Material, Tag, Technique


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name",)


for model in (Material, Technique, Tag):
    admin.site.register(model, list_display=("name", "is_active", "sort_order"), search_fields=("name",))

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from .models import Category


def active_category_tree() -> QuerySet[Category]:
    children = Category.objects.filter(is_active=True).order_by("sort_order", "name")
    return (
        Category.objects.filter(is_active=True, parent__isnull=True)
        .prefetch_related(Prefetch("children", queryset=children))
        .order_by("sort_order", "name")
    )


def category_with_descendants(slug: str) -> list[int]:
    category = Category.objects.filter(slug=slug).only("id").first()
    if category is None:
        return []
    return [category.pk, *Category.objects.filter(parent_id=category.pk).values_list("pk", flat=True)]

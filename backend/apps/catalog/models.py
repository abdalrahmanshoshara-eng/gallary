"""
Dynamic classification data (PMP §10, BR-106/107). Never hard-coded: the initial values
are a data migration and staff manage them afterwards. Terms in use are deactivated,
not deleted.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class Term(models.Model):
    name = models.CharField("الاسم", max_length=100)
    slug = models.SlugField("المعرّف", max_length=120, unique=True, allow_unicode=True)
    is_active = models.BooleanField("فعّال", default=True)
    sort_order = models.PositiveIntegerField("الترتيب", default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Category(Term):
    """Two levels: main categories and their sub-categories."""

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children", verbose_name="التصنيف الأب"
    )
    description = models.TextField("الوصف", blank=True)

    class Meta(Term.Meta):
        verbose_name = "تصنيف"
        verbose_name_plural = "التصنيفات"
        constraints = [
            models.CheckConstraint(condition=~models.Q(parent=models.F("id")), name="category_not_own_parent"),
        ]


class Material(Term):
    class Meta(Term.Meta):
        verbose_name = "مادة"
        verbose_name_plural = "المواد"


class Technique(Term):
    class Meta(Term.Meta):
        verbose_name = "تقنية"
        verbose_name_plural = "التقنيات"


class Tag(Term):
    class Meta(Term.Meta):
        verbose_name = "وسم"
        verbose_name_plural = "الوسوم"

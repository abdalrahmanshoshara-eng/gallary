"""
Keep artwork search keys fresh when something they include is renamed elsewhere
(an artist, a category, a material, a technique or a tag). Runs after commit in Celery,
so a rename never waits for re-indexing.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.artists.models import Artist
from apps.catalog.models import Category, Material, Tag, Technique

from .tasks import refresh_search_text_task

RELATION = {Artist: "artist", Category: "category", Material: "materials", Technique: "techniques", Tag: "tags"}


def _on_rename(sender, instance, created, update_fields=None, **kwargs):
    if created or (update_fields is not None and "name" not in update_fields):
        return
    transaction.on_commit(lambda: refresh_search_text_task.delay(RELATION[sender], instance.pk))


for model in RELATION:
    receiver(post_save, sender=model, dispatch_uid=f"artwork-search-{model.__name__}")(_on_rename)

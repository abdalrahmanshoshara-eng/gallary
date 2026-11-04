from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.artworks.models import Artwork

from .models import Favorite


def add(user, artwork: Artwork) -> bool:
    """Idempotent; returns True when newly added."""
    try:
        with transaction.atomic():
            Favorite.objects.create(user=user, artwork=artwork)
    except IntegrityError:
        return False
    return True


def remove(user, artwork: Artwork) -> None:
    Favorite.objects.filter(user=user, artwork=artwork).delete()

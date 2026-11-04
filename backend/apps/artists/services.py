from __future__ import annotations

from django.db import transaction

from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.core.slugs import unique_slug
from apps.media import services as media
from apps.media.models import ImagePurpose

from .models import Artist

_AUDITED = ("name", "status", "is_featured", "slug")


class ArtistHasArtworksError(ConflictError):
    code = "ARTIST_HAS_ARTWORKS"
    message = "لا يمكن حذف فنان مرتبط بأعمال فنية. يمكنك إخفاؤه بدلاً من ذلك."


@transaction.atomic
def create_artist(*, actor, data: dict) -> Artist:
    slug = data.pop("slug", "") or unique_slug(Artist, data["name"])
    artist = Artist.objects.create(slug=slug, created_by=actor, **data)
    audit.record(actor=actor, action="artist.created", entity=artist, changes={"name": artist.name})
    return artist


@transaction.atomic
def update_artist(artist: Artist, *, actor, data: dict) -> Artist:
    changes = {}
    for field, value in data.items():
        old = getattr(artist, field)
        if old != value:
            if field in _AUDITED:
                changes[field] = {"from": old, "to": value}
            setattr(artist, field, value)
    artist.save()
    if changes:
        audit.record(actor=actor, action="artist.updated", entity=artist, changes=changes)
    return artist


@transaction.atomic
def set_photo(artist: Artist, upload, *, actor) -> Artist:
    old = artist.photo
    artist.photo = media.ingest_image(upload, purpose=ImagePurpose.ARTIST, user=actor)
    artist.save(update_fields=["photo", "updated_at"])
    if old is not None:
        media.delete_asset(old)
    return artist


@transaction.atomic
def remove_photo(artist: Artist, *, actor) -> Artist:
    if artist.photo is not None:
        old = artist.photo
        artist.photo = None
        artist.save(update_fields=["photo", "updated_at"])
        media.delete_asset(old)
    return artist


@transaction.atomic
def delete_artist(artist: Artist, *, actor) -> None:
    if artist.artworks.exists() or artist.executed_artworks.exists():
        raise ArtistHasArtworksError()
    audit.record(actor=actor, action="artist.deleted", entity=artist, changes={"name": artist.name})
    photo = artist.photo
    artist.delete()
    if photo is not None:
        media.delete_asset(photo)

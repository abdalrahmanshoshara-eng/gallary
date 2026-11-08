from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.core.slugs import unique_slug
from apps.media import services as media
from apps.media.models import ImagePurpose

from .models import AgreementStatus, Artist, ArtistAgreement

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


# --- commission agreements (BR-701) ---------------------------------------------------------------
def active_agreement(artist_id: int | None) -> ArtistAgreement | None:
    if artist_id is None:
        return None
    return ArtistAgreement.objects.filter(artist_id=artist_id, status=AgreementStatus.ACTIVE).first()


def _end(agreement: ArtistAgreement, actor) -> None:
    today = timezone.localdate()
    agreement.status = AgreementStatus.ENDED
    agreement.effective_to = max(today, agreement.effective_from)
    agreement.ended_by = actor if getattr(actor, "pk", None) else None
    agreement.save(update_fields=["status", "effective_to", "ended_by"])


@transaction.atomic
def create_agreement(artist: Artist, *, actor, commission_rate: Decimal, notes: str = "") -> ArtistAgreement:
    """A new agreement takes effect today and ends the current one (one active per artist)."""
    if not (Decimal(0) <= commission_rate <= Decimal(100)):
        raise ConflictError(
            "النسبة بين 0 و100.", code="VALIDATION_ERROR", http_status=400, details={"commission_rate": ["0–100"]}
        )
    artist = Artist.objects.select_for_update().get(pk=artist.pk)  # serialises concurrent changes
    previous = active_agreement(artist.pk)
    if previous is not None:
        _end(previous, actor)
    agreement = ArtistAgreement.objects.create(
        artist=artist, commission_rate=commission_rate, notes=notes.strip(), created_by=actor
    )
    audit.record(
        actor=actor,
        action="artist.agreement_created",
        entity=artist,
        changes={
            "commission_rate": {"from": str(previous.commission_rate) if previous else None, "to": str(commission_rate)}
        },
    )
    return agreement


@transaction.atomic
def end_agreement(artist: Artist, *, actor) -> None:
    artist = Artist.objects.select_for_update().get(pk=artist.pk)
    agreement = active_agreement(artist.pk)
    if agreement is None:
        raise ConflictError("لا توجد اتفاقية نشطة لهذا الفنان.", code="NO_ACTIVE_AGREEMENT")
    _end(agreement, actor)
    audit.record(
        actor=actor,
        action="artist.agreement_ended",
        entity=artist,
        changes={"commission_rate": {"from": str(agreement.commission_rate), "to": None}},
    )

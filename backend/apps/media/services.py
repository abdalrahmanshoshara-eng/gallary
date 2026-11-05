"""Image ingestion and lifecycle."""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from .models import ImageAsset, ImagePurpose
from .processing import inspect_upload
from .storage import private_storage


def _key_prefix(asset: ImageAsset) -> str:
    created = asset.created_at
    return f"images/{created:%Y/%m}/{asset.public_id}"


def ingest_image(upload: UploadedFile, *, purpose: ImagePurpose, user=None) -> ImageAsset:
    """
    Validate an upload, store the untouched original privately and queue processing.
    Must be called inside the caller's transaction; processing starts after commit.
    """
    from .tasks import process_image

    data = upload.read()
    info = inspect_upload(data)
    asset = ImageAsset(
        purpose=purpose,
        original_content_type=info.content_type,
        original_bytes=len(data),
        width=info.width,
        height=info.height,
        created_by=user if getattr(user, "pk", None) else None,
        created_at=timezone.now(),
    )
    key = f"{_key_prefix(asset)}/original.{info.extension}"
    asset.original_key = private_storage().save(key, ContentFile(data))
    asset.save()
    transaction.on_commit(lambda: process_image.apply_async(args=[asset.pk], queue="media"))
    return asset


def copy_image(asset: ImageAsset, *, purpose: ImagePurpose, user=None) -> ImageAsset:
    """A new asset from another asset's original (e.g. auction-request photos reused for the
    artwork), so each owner keeps its own lifecycle."""
    with private_storage().open(asset.original_key, "rb") as source:
        data = source.read()
    upload = ContentFile(data, name=asset.original_key.rsplit("/", 1)[-1])
    return ingest_image(upload, purpose=purpose, user=user)


def delete_asset(asset: ImageAsset) -> None:
    """Delete the row now and the stored files after commit (never the other way round)."""
    from .tasks import delete_files

    public_keys = asset.variant_keys()
    private_keys = [asset.original_key]
    asset.delete()
    transaction.on_commit(lambda: delete_files.apply_async(args=[public_keys, private_keys], queue="media"))


def variant_key(asset: ImageAsset, label: str) -> str:
    return f"{_key_prefix(asset)}/w{label}.webp"

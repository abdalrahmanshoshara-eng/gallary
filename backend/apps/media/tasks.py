from __future__ import annotations

import logging

from celery import shared_task
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .errors import InvalidImageError
from .models import ImageAsset, ImageStatus
from .processing import render_variants
from .storage import private_storage, public_storage

logger = logging.getLogger(__name__)


@shared_task(name="apps.media.tasks.process_image", bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def process_image(self, asset_id: int) -> None:
    """Generate public WebP variants. Idempotent: re-running overwrites nothing valid."""
    from .services import variant_key

    asset = ImageAsset.objects.filter(pk=asset_id).first()
    if asset is None or asset.status == ImageStatus.READY:
        return
    try:
        with private_storage().open(asset.original_key, "rb") as handle:
            original = handle.read()
    except OSError as exc:  # storage unavailable: retry later
        raise self.retry(exc=exc) from exc
    try:
        rendered = render_variants(original)
    except InvalidImageError as exc:  # permanent: never retried
        ImageAsset.objects.filter(pk=asset_id).update(status=ImageStatus.FAILED, error=exc.code)
        return

    storage = public_storage()
    variants = {}
    for variant in rendered:
        key = variant_key(asset, variant.label)
        if storage.exists(key):
            storage.delete(key)
        stored = storage.save(key, ContentFile(variant.data))
        variants[variant.label] = {"key": stored, "width": variant.width, "height": variant.height}

    with transaction.atomic():
        updated = ImageAsset.objects.filter(pk=asset_id).update(
            variants=variants, status=ImageStatus.READY, error="", processed_at=timezone.now()
        )
    if not updated:  # deleted while processing: remove what we just wrote
        for v in variants.values():
            storage.delete(v["key"])


@shared_task(name="apps.media.tasks.delete_files", acks_late=True)
def delete_files(public_keys: list[str], private_keys: list[str]) -> None:
    for storage, keys in ((public_storage(), public_keys), (private_storage(), private_keys)):
        for key in keys:
            try:
                storage.delete(key)
            except OSError:
                logger.warning("media_delete_failed", extra={"key": key})

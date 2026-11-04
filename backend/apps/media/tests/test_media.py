import io

import pytest
from django.test import override_settings
from PIL import Image

from apps.media import services
from apps.media.errors import ImageTooLargeError, ImageTooSmallError, InvalidImageError
from apps.media.models import ImageAsset, ImagePurpose, ImageStatus
from apps.media.processing import inspect_upload, render_variants
from apps.media.storage import private_storage, public_storage
from conftest import make_image_bytes


# --- validation (BR-108) -------------------------------------------------------------------
@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_accepted_formats(fmt):
    info = inspect_upload(make_image_bytes(fmt))
    assert (info.width, info.height) == (1200, 800)


def test_content_not_extension_decides():
    with pytest.raises(InvalidImageError):
        inspect_upload(b"%PDF-1.7 definitely not an image")
    gif = io.BytesIO()
    Image.new("RGB", (500, 500)).save(gif, format="GIF")
    with pytest.raises(InvalidImageError):
        inspect_upload(gif.getvalue())


def test_truncated_image_is_rejected():
    with pytest.raises(InvalidImageError):
        inspect_upload(make_image_bytes()[:2000])


def test_too_small_and_too_large():
    with pytest.raises(ImageTooSmallError):
        inspect_upload(make_image_bytes(size=(1000, 200)))
    with override_settings(IMAGE_UPLOAD_MAX_BYTES=1000), pytest.raises(ImageTooLargeError):
        inspect_upload(make_image_bytes())


def test_exif_orientation_is_applied_to_dimensions():
    info = inspect_upload(make_image_bytes(size=(1200, 800), orientation=6))  # rotated 90°
    assert (info.width, info.height) == (800, 1200)


# --- variants -------------------------------------------------------------------------------
def test_variants_are_webp_without_metadata_and_never_upscaled():
    variants = render_variants(make_image_bytes(size=(1600, 1000), gps=True))
    assert [(v.label, v.width) for v in variants] == [("400", 400), ("1000", 1000), ("2000", 1600)]
    for v in variants:
        with Image.open(io.BytesIO(v.data)) as image:
            assert image.format == "WEBP"
            assert not image.getexif()  # GPS and all EXIF stripped
            assert abs(image.height / image.width - 1000 / 1600) < 0.01  # aspect kept, no crop


def test_small_original_collapses_to_one_variant():
    variants = render_variants(make_image_bytes(size=(350, 500)))
    assert [(v.label, v.width, v.height) for v in variants] == [("400", 350, 500)]


def test_transparency_is_preserved():
    variants = render_variants(make_image_bytes("PNG", size=(600, 600), mode="RGBA"))
    with Image.open(io.BytesIO(variants[0].data)) as image:
        assert image.mode == "RGBA"


# --- lifecycle ------------------------------------------------------------------------------
@pytest.mark.django_db
def test_ingest_keeps_original_private_and_publishes_variants(image_file, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        asset = services.ingest_image(image_file(gps=True), purpose=ImagePurpose.ARTWORK)
    asset.refresh_from_db()
    assert asset.status == ImageStatus.READY
    assert private_storage().exists(asset.original_key)
    assert not public_storage().exists(asset.original_key)
    assert set(asset.variants) == {"400", "1000", "2000"}
    for v in asset.variants.values():
        assert public_storage().exists(v["key"]) and v["key"].endswith(".webp")
    # The original keeps the uploaded bytes (master copy for future re-processing).
    with private_storage().open(asset.original_key) as f:
        assert Image.open(f).getexif().get(0x8825) is not None


@pytest.mark.django_db
def test_processing_failure_marks_asset_failed(django_capture_on_commit_callbacks):
    from django.core.files.base import ContentFile

    key = private_storage().save("images/broken/original.jpg", ContentFile(b"garbage"))
    asset = ImageAsset.objects.create(
        purpose=ImagePurpose.ARTWORK,
        original_key=key,
        original_content_type="image/jpeg",
        original_bytes=7,
        width=1,
        height=1,
    )
    from apps.media.tasks import process_image

    process_image.delay(asset.pk)
    asset.refresh_from_db()
    assert asset.status == ImageStatus.FAILED and asset.error == "INVALID_IMAGE"


@pytest.mark.django_db
def test_delete_removes_files_after_commit(image_file, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        asset = services.ingest_image(image_file(), purpose=ImagePurpose.ARTWORK)
    asset.refresh_from_db()
    keys = asset.variant_keys()
    original = asset.original_key
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_asset(asset)
    assert not ImageAsset.objects.exists()
    assert not private_storage().exists(original)
    assert not any(public_storage().exists(k) for k in keys)


@pytest.mark.django_db
def test_files_survive_a_rolled_back_delete(image_file, django_capture_on_commit_callbacks):
    from django.db import transaction

    with django_capture_on_commit_callbacks(execute=True):
        asset = services.ingest_image(image_file(), purpose=ImagePurpose.ARTWORK)
    asset.refresh_from_db()
    with pytest.raises(RuntimeError), transaction.atomic():
        services.delete_asset(asset)
        raise RuntimeError
    assert private_storage().exists(asset.original_key)

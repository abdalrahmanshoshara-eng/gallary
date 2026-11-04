"""Pure image operations (no storage, no database) — easy to test."""

from __future__ import annotations

import io
from dataclasses import dataclass

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ImageTooLargeError, ImageTooSmallError, InvalidImageError

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


@dataclass(frozen=True)
class InspectedImage:
    format: str
    content_type: str
    extension: str
    width: int
    height: int


def inspect_upload(data: bytes) -> InspectedImage:
    """
    Validate by content, never by file name or declared content type (BR-108).
    Returns dimensions after EXIF orientation is applied.
    """
    if len(data) > settings.IMAGE_UPLOAD_MAX_BYTES:
        mb = settings.IMAGE_UPLOAD_MAX_BYTES // (1024 * 1024)
        raise ImageTooLargeError(
            f"حجم الصورة أكبر من {mb} ميغابايت.", details={"max_bytes": settings.IMAGE_UPLOAD_MAX_BYTES}
        )
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            if fmt not in ALLOWED_FORMATS:
                raise InvalidImageError()
            if probe.width * probe.height > settings.IMAGE_MAX_PIXELS:
                raise ImageTooLargeError("أبعاد الصورة كبيرة جداً.")
            probe.verify()  # structural check; the image must be reopened after verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # full decode catches truncated files
            oriented = ImageOps.exif_transpose(image)
            width, height = oriented.size
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError() from exc
    if min(width, height) < settings.IMAGE_MIN_SIDE_PX:
        raise ImageTooSmallError(
            f"يجب ألا يقل أصغر بُعد للصورة عن {settings.IMAGE_MIN_SIDE_PX} بكسل.",
            details={"min_side_px": settings.IMAGE_MIN_SIDE_PX},
        )
    return InspectedImage(fmt, ALLOWED_FORMATS[fmt], EXTENSIONS[fmt], width, height)


@dataclass(frozen=True)
class RenderedVariant:
    label: str
    width: int
    height: int
    data: bytes


def render_variants(original: bytes) -> list[RenderedVariant]:
    """
    Resize to each configured width without cropping (artworks are never cut — PMP §3.5),
    never upscaling, and re-encode as WebP. Re-encoding drops all metadata (EXIF/GPS).
    Widths larger than the original collapse into one variant at the original size.
    """
    try:
        return _render(original)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError() from exc


def _render(original: bytes) -> list[RenderedVariant]:
    with Image.open(io.BytesIO(original)) as image:
        image = ImageOps.exif_transpose(image)
        has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
        image = image.convert("RGBA" if has_alpha else "RGB")
        variants: list[RenderedVariant] = []
        seen_widths: set[int] = set()
        for target in sorted(settings.IMAGE_VARIANT_WIDTHS):
            width = min(target, image.width)
            if width in seen_widths:
                continue
            seen_widths.add(width)
            height = max(1, round(image.height * width / image.width))
            resized = image if width == image.width else image.resize((width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="WEBP", quality=settings.IMAGE_VARIANT_QUALITY, method=6)
            variants.append(RenderedVariant(str(target), width, height, buffer.getvalue()))
        return variants

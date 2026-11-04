"""Unique, URL-safe slugs that keep Arabic letters (e.g. "لوحة-الياسمين")."""

from __future__ import annotations

import re
import uuid

from django.db import models
from django.utils.text import slugify

_ARABIC_MARKS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")  # tashkeel + tatweel


def make_slug(text: str, max_length: int = 200) -> str:
    cleaned = _ARABIC_MARKS.sub("", text or "")
    slug = slugify(cleaned, allow_unicode=True)[:max_length].strip("-")
    return slug or uuid.uuid4().hex[:10]


def unique_slug(
    model: type[models.Model], text: str, *, field: str = "slug", exclude_pk=None, max_length: int = 200
) -> str:
    base = make_slug(text, max_length=max_length - 6)
    candidate, n = base, 2
    qs = model._default_manager.all()
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(**{field: candidate}).exists():
        candidate = f"{base}-{n}"
        n += 1
    return candidate

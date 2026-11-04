"""
Search key for artworks (§21): title, creator, description, category (and its parent),
materials, techniques and tags — normalised with core.arabic. Works on real and historical
(migration) models alike, since it only reads plain attributes.
"""

from __future__ import annotations

from apps.core.arabic import normalize_arabic

DESCRIPTION_CHARS = 2000  # long biographies/descriptions add noise and index size, not recall


def build_search_text(artwork) -> str:
    parts = [artwork.title, artwork.creator_name_override]
    if artwork.artist_id:
        parts.append(artwork.artist.name)
    if artwork.category_id:
        parts.append(artwork.category.name)
        if artwork.category.parent_id:
            parts.append(artwork.category.parent.name)
    if artwork.pk:
        for relation in ("materials", "techniques", "tags"):
            parts.extend(term.name for term in getattr(artwork, relation).all())
    parts.append((artwork.description or "")[:DESCRIPTION_CHARS])
    return normalize_arabic(" | ".join(p for p in parts if p))

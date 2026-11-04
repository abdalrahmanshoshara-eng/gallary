"""
Arabic text normalisation for search (PROJECT_MASTER_PROMPT §21).

Only search keys are normalised; stored/displayed text is never changed. The same function
is applied to the indexed text and to the user's query, so these variants all match:

    أ إ آ ٱ → ا      ى → ي      ة → ه      ؤ → و      ئ → ي
    tashkeel and tatweel removed, Arabic-Indic digits → Latin, Latin lower-cased.
"""

from __future__ import annotations

import re

_MARKS = re.compile(
    r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]"
)  # tashkeel, Quranic marks, superscript alef, tatweel
_TABLE = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        **{chr(0x0660 + i): str(i) for i in range(10)},  # ٠-٩
        **{chr(0x06F0 + i): str(i) for i in range(10)},  # ۰-۹ (Persian)
    }
)
_SPACES = re.compile(r"\s+")


def normalize_arabic(text: str | None) -> str:
    if not text:
        return ""
    return _SPACES.sub(" ", _MARKS.sub("", text).translate(_TABLE).lower()).strip()


def search_terms(query: str | None, *, max_terms: int = 8) -> list[str]:
    """Normalised, de-duplicated words of a user query (bounded to keep queries cheap)."""
    seen: list[str] = []
    for word in normalize_arabic(query).split(" "):
        word = word.strip(".,،؛:!?؟\"'()[]")
        if word and word not in seen:
            seen.append(word)
    return seen[:max_terms]

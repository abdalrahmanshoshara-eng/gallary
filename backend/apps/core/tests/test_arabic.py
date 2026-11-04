import pytest

from apps.core.arabic import normalize_arabic, search_terms


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("أحمد", "احمد"),
        ("إبراهيم", "ابراهيم"),
        ("آمال", "امال"),
        ("مصطفى", "مصطفي"),
        ("لوحة", "لوحه"),
        ("مُؤْتَمَر", "موتمر"),
        ("شـــام", "شام"),
        ("عام ٢٠٢٤", "عام 2024"),
        ("Oil  ON Canvas", "oil on canvas"),
    ],
)
def test_variants_normalise_to_the_same_key(a, b):
    assert normalize_arabic(a) == normalize_arabic(b)


def test_search_terms_are_bounded_and_deduplicated():
    assert search_terms("  لوحة، لوحه زيت؟ ") == ["لوحه", "زيت"]
    assert len(search_terms(" ".join(f"w{i}" for i in range(20)))) == 8
    assert search_terms("") == []

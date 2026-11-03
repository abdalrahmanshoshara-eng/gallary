import pytest

from apps.accounts.phone import InvalidPhoneError, mask_phone, normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["0944567890", "0944 567 890", "+963944567890", "00963944567890", "٠٩٤٤٥٦٧٨٩٠", "+963 944-567-890"],
)
def test_syrian_inputs_normalise_to_e164(raw):
    assert normalize_phone(raw) == "+963944567890"


def test_international_numbers_keep_their_country():
    assert normalize_phone("+971501234567") == "+971501234567"


@pytest.mark.parametrize("raw", ["", "   ", "abc", "123", "+96391", "09123"])
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)


def test_mask_phone():
    assert mask_phone("+963944567890") == "+963•••890"

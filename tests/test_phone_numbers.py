import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.phone_numbers import MobileNumber, PhoneNumber


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" 987 654 321 ", "+51987654321"),
        ("+1 (202) 555-0100", "+12025550100"),
        ("(01) 234-5678", "+5112345678"),
    ],
)
def test_normalizes_valid_phone_numbers(raw, expected):
    assert TypeAdapter(PhoneNumber).validate_python(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "987654321 texto", "+999123456789"])
def test_rejects_invalid_phone_numbers(raw):
    with pytest.raises(ValidationError):
        TypeAdapter(PhoneNumber).validate_python(raw)


def test_mobile_field_rejects_peruvian_landline():
    with pytest.raises(ValidationError):
        TypeAdapter(MobileNumber).validate_python("(01) 234-5678")

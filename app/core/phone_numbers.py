import re
from typing import Annotated

import phonenumbers
from pydantic import AfterValidator, StringConstraints

PHONE_PATTERN = re.compile(r"\+?[0-9(). -]+")


def parse_phone(value: str) -> phonenumbers.PhoneNumber:
    if PHONE_PATTERN.fullmatch(value) is None:
        raise ValueError("Ingresa un número de teléfono válido.")
    try:
        number = phonenumbers.parse(value, "PE")
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Ingresa un número de teléfono válido.") from exc
    if not phonenumbers.is_valid_number(number):
        raise ValueError("Ingresa un número de teléfono válido.")
    return number


def normalize_phone(value: str) -> str:
    number = parse_phone(value)
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def normalize_mobile(value: str) -> str:
    number = parse_phone(value)
    if phonenumbers.number_type(number) not in (
        phonenumbers.PhoneNumberType.MOBILE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    ):
        raise ValueError("Ingresa un número de celular válido.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


PhoneNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=32), AfterValidator(normalize_phone)
]
MobileNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=32), AfterValidator(normalize_mobile)
]

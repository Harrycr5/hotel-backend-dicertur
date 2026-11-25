from enum import StrEnum
from typing import Self


class LabeledTextChoice(StrEnum):
    def __new__(cls, value: str, label: str) -> Self:
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        return member

    label: str

    @classmethod
    def choices(cls) -> list[dict[str, str]]:
        return [{"value": member.value, "label": member.label} for member in cls]


class DocumentType(LabeledTextChoice):
    NO_DOCUMENT = "SIN DOCUMENTO", "Sin Documento"
    DNI = "DNI", "Dni"
    RUC = "RUC", "Ruc"
    FOREIGNER_CARD = "CARNET DE EXTRANJERIA", "Carnet De Extranjeria"
    PASSPORT = "PASAPORTE", "Pasaporte"

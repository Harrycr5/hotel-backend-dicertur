from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.core.document_types import DocumentType
from app.core.phone_numbers import MobileNumber

from .choices import PersonArea, PersonCategory, PersonGender

PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PersonNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PersonName
    last_name: PersonName
    document_type: DocumentType
    document_number: PersonNumber | None = None
    mobile_phone: MobileNumber
    area: PersonArea
    gender: PersonGender
    category: PersonCategory
    is_permanent_employee: bool = False


class PersonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PersonName | None = None
    last_name: PersonName | None = None
    document_type: DocumentType | None = None
    document_number: PersonNumber | None = None
    mobile_phone: MobileNumber | None = None
    area: PersonArea | None = None
    gender: PersonGender | None = None
    category: PersonCategory | None = None
    is_permanent_employee: bool | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para actualizar.")
        for field in self.model_fields_set - {"document_number"}:
            if getattr(self, field) is None:
                raise ValueError(f"El campo {field} no acepta null.")
        return self


class PersonRead(PersonCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mobile_phone: str
    created_at: datetime
    updated_at: datetime


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: DocumentType
    document_number: str | None
    name: str
    last_name: str | None
    phone: str
    email: str
    country_code: str
    reservation_count: int
    city: str
    district_code: str | None
    address: str
    is_active: bool


class ChoiceRead(BaseModel):
    value: str
    label: str


class PersonChoicesRead(BaseModel):
    document_types: list[ChoiceRead]
    areas: list[ChoiceRead]
    genders: list[ChoiceRead]
    categories: list[ChoiceRead]

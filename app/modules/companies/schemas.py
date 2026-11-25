from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, model_validator

from app.core.phone_numbers import PhoneNumber
from app.modules.ubigee.schemas import DistrictCode

Ruc = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{11}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Link = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
Email = Annotated[EmailStr, StringConstraints(max_length=254)]


class CompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruc: Ruc
    legal_name: Name
    trade_name: Name | None = None
    lodging_class: Reference | None = None
    category: Reference | None = None
    certificate_number: Reference | None = None
    address: Address
    district_code: DistrictCode
    phone: PhoneNumber | None = None
    coordinate_system: Reference | None = None
    website: Link | None = None
    reservations_email: Email | None = None
    contact_name: Name | None = None
    contact_phone: PhoneNumber | None = None
    contact_email: Email | None = None
    national_hotel_chain: bool = False
    international_hotel_chain: bool = False


class BranchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    trade_name: Name | None = None
    address: Address
    district_code: DistrictCode
    email: Email | None = None
    phone: PhoneNumber | None = None
    logo: Link | None = None
    logo_ticket: Link | None = None


def validate_patch(data: BaseModel, non_nullable: set[str]) -> None:
    if not data.model_fields_set:
        raise ValueError("Envía al menos un campo para actualizar.")
    for field in sorted(data.model_fields_set & non_nullable):
        if getattr(data, field) is None:
            raise ValueError(f"El campo {field} no acepta null.")


class CompanyUpdate(CompanyCreate):
    ruc: Ruc | None = None
    legal_name: Name | None = None
    address: Address | None = None
    district_code: DistrictCode | None = None
    national_hotel_chain: bool | None = None
    international_hotel_chain: bool | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        validate_patch(
            self,
            {
                "ruc",
                "legal_name",
                "address",
                "district_code",
                "national_hotel_chain",
                "international_hotel_chain",
            },
        )
        return self


class BranchUpdate(BranchCreate):
    name: Name | None = None
    address: Address | None = None
    district_code: DistrictCode | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        validate_patch(self, {"name", "address", "district_code"})
        return self


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str


class ProvinceLocationRead(LocationRead):
    department: LocationRead


class DistrictLocationRead(LocationRead):
    province: ProvinceLocationRead


class CompanyRead(CompanyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str | None = None
    contact_phone: str | None = None
    district: DistrictLocationRead
    created_at: datetime
    updated_at: datetime


class BranchRead(BranchCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str | None = None
    company_id: UUID
    district: DistrictLocationRead
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

from .choices import RoomStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Condition = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
BedPlaces = Annotated[int, Field(ge=1, le=2_147_483_647)]
Price = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class RoomTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    has_bathroom: bool | None = None
    bed_places: BedPlaces | None = None


class RoomTypeUpdate(RoomTypeCreate):
    name: Name | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        validate_patch(self, ("name",))
        return self


class RoomTypeRead(RoomTypeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class RateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    rate_condition: Condition | None = None
    is_active: bool = True
    price: Price


class RateUpdate(RateCreate):
    name: Name | None = None
    is_active: bool | None = None
    price: Price | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        validate_patch(self, ("name", "is_active", "price"))
        return self


class RateRead(RateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class FloorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Name


class FloorRead(FloorCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class RoomDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: Name
    description: Annotated[str, StringConstraints(max_length=2000)] | None = None


RoomCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
RoomDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    code: RoomCode
    description: RoomDescription | None = None
    status: RoomStatus = RoomStatus.AVAILABLE
    visible: bool = True
    room_type_id: UUID
    category_id: UUID | None = None
    floor_id: UUID
    rate_ids: list[UUID] = Field(default_factory=list)
    details: list[RoomDetail] = Field(default_factory=list)


class RoomUpdate(RoomCreate):
    name: Name | None = None
    code: RoomCode | None = None
    status: RoomStatus | None = None
    visible: bool | None = None
    room_type_id: UUID | None = None
    floor_id: UUID | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        validate_patch(self, ("name", "code", "status", "visible", "room_type_id", "floor_id"))
        return self


class RoomCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class RoomStatusChoice(BaseModel):
    value: RoomStatus
    label: str


class RoomImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID = Field(exclude=True)

    @computed_field
    @property
    def image(self) -> str:
        return f"/api/v1/rooms/{self.room_id}/images/{self.id}"


class RoomRead(RoomCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    images: list[RoomImageRead]
    created_at: datetime
    updated_at: datetime


def validate_patch(data: BaseModel, required_fields: tuple[str, ...]) -> None:
    if not data.model_fields_set:
        raise ValueError("Envía al menos un campo para actualizar.")
    for field in required_fields:
        if field in data.model_fields_set and getattr(data, field) is None:
            raise ValueError(f"El campo {field} no acepta null.")

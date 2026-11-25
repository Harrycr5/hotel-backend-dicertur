from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from .models import Direction


def cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2), AfterValidator(cents)]
PositiveMoney = Annotated[Money, Field(gt=0)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
ConceptCode = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=50, pattern=r"^[A-Z0-9_]+$")
]


class TillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    is_active: bool = True


class TillRead(TillCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class ConceptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ConceptCode
    name: Name
    is_active: bool = True


class ConceptRead(ConceptCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class ShiftOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_amount: Money


class ShiftClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: Money


class ShiftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    till_id: UUID
    opened_by_id: UUID
    opened_at: datetime
    opening_amount: Decimal
    closed_by_id: UUID | None
    closed_at: datetime | None
    counted_cash: Decimal | None
    expected_cash: Decimal | None
    difference: Decimal | None


class MovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: UUID
    payment_method_id: UUID
    direction: Direction
    amount: PositiveMoney
    notes: Notes | None = None
    reservation_id: UUID | None = None
    stay_id: UUID | None = None
    consumption_id: UUID | None = None
    charge_id: Name | None = None


class MovementRead(MovementCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    registered_by_id: UUID
    transfer_id: UUID | None
    created_at: datetime
    voided_at: datetime | None
    voided_by_id: UUID | None
    void_reason: str | None


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_shift_id: UUID
    destination_shift_id: UUID
    amount: PositiveMoney
    notes: Notes | None = None


class TransferRead(BaseModel):
    id: UUID
    expense: MovementRead
    income: MovementRead


class VoidMovement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Notes


class VoidRead(BaseModel):
    movements: list[MovementRead]

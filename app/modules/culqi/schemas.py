from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints

ChargeID = Annotated[
    str, StringConstraints(pattern=r"^chr_(test|live)_[A-Za-z0-9]+$", max_length=100)
]


class ChargeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    token: SecretStr
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    device_id: UUID | None = None


class ChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reservation_id: UUID
    amount: Decimal
    status: str
    provider_charge_id: str | None


class ThreeDS(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eci: str = Field(min_length=1, max_length=10)
    xid: str = Field(min_length=1, max_length=128)
    cavv: str = Field(min_length=1, max_length=128)
    protocolVersion: str = Field(min_length=1, max_length=20)
    directoryServerTransactionId: UUID


class AuthenticateCharge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr
    authentication: ThreeDS


class ReconcileCharge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_charge_id: ChargeID

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.core.document_types import DocumentType
from app.core.phone_numbers import PhoneNumber

from .choices import ReservationStatus

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
DocumentNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
]
Locality = Annotated[str, StringConstraints(max_length=150)]
Reference = Annotated[str, StringConstraints(max_length=100)]
RequiredLocality = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
RequiredLongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Ruc = Annotated[str, StringConstraints(pattern=r"^[0-9]{11}$")]
CountryCode = Annotated[str, StringConstraints(to_upper=True, pattern=r"^[a-zA-Z]{2}$")]
PERU_TIME = timezone(timedelta(hours=-5))


def parse_local_datetime(value):
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%d-%m-%Y %H:%M")
        except ValueError:
            pass
    return value


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=PERU_TIME)
    return value.astimezone(timezone.utc)


def parse_local_date(value):
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            pass
    return value


ReservationDateTime = Annotated[
    datetime, BeforeValidator(parse_local_datetime), AfterValidator(as_utc)
]
BirthDate = Annotated[date, BeforeValidator(parse_local_date)]


class CompanionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    document_number: DocumentNumber
    full_name: Name
    birth_date: BirthDate | None = None
    phone: PhoneNumber | None = None
    email: EmailStr | None = None


class CompanionRead(CompanionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str | None = None


class DetailCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_paid: Money = Decimal("0.00")
    amount_remaining: Money
    base_price: Money
    promotion_discount: Money = Decimal("0.00")
    final_total: Money
    customer_document_number: DocumentNumber | None = None
    customer_name: Name | None = None
    customer_phone: PhoneNumber | None = None
    customer_email: EmailStr | None = None
    room_name: Locality | None = None
    stay_days: int = Field(ge=1, le=2_147_483_647)
    unit_rate: Money
    created_at: ReservationDateTime | None = None

    @model_validator(mode="after")
    def validate_balance(self):
        if self.amount_paid + self.amount_remaining != self.final_total:
            raise ValueError("Lo pagado y lo restante deben sumar el total final.")
        return self


class DetailRead(DetailCreate):
    model_config = ConfigDict(from_attributes=True)

    reservation_id: UUID
    customer_phone: str | None = None
    created_at: datetime


class ReservationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: UUID
    rate_id: UUID
    document_type: DocumentType
    document_number: DocumentNumber | None = None
    full_name: Name
    birth_date: BirthDate
    phone: PhoneNumber
    email: EmailStr
    is_active: bool = True
    status: ReservationStatus = ReservationStatus.BOOKED
    country_code: CountryCode
    city: RequiredLocality
    region: RequiredLocality
    district: RequiredLocality
    address: RequiredLongText
    travel_reason: Name
    dietary_restrictions: RequiredLongText
    gender: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    payment_method_id: UUID | None = None
    payment_amount: Money | None = None
    transaction_number: Reference | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None
    company_name: Name | None = None
    ruc: Ruc | None = None
    discount_code: Reference | None = None


class ReservationCreate(ReservationFields):
    check_in: ReservationDateTime
    check_out: ReservationDateTime
    paid_at: ReservationDateTime | None = None
    created_at: ReservationDateTime | None = None
    companions: list[CompanionCreate] = Field(default_factory=list)
    detail: DetailCreate | None = None

    @model_validator(mode="after")
    def validate_stay(self):
        if self.check_out <= self.check_in:
            raise ValueError("La salida debe ser posterior a la entrada.")
        return self


class ReservationRead(ReservationFields):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    check_in: datetime
    check_out: datetime
    paid_at: datetime | None
    created_at: datetime
    companions: list[CompanionRead]
    detail: DetailRead | None
    room_name: str
    room_type_name: str
    rate_name: str


class PaymentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_paid: Money = Field(gt=0, description="Monto total acumulado pagado por la reserva.")
    method_id: UUID | None = None
    transaction_number: Reference | None = None
    paid_at: ReservationDateTime | None = None


class ReservationStatusRead(BaseModel):
    value: ReservationStatus
    label: str


class ReservationPaymentMethodRead(BaseModel):
    id: UUID
    code: str
    name: str
    payment_count: int
    amount_paid: Decimal


class ReservationPaymentsRead(BaseModel):
    reservation_id: UUID
    payment_method_count: int
    methods: list[ReservationPaymentMethodRead]
    unattributed_amount: Decimal

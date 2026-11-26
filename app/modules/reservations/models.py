from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.document_types import DocumentType
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.person.choices import PersonGender
from app.modules.person.models import text_choices
from app.modules.rooms.models import Rate, Room

from .choices import ReservationStatus


def document_type_column():
    return Enum(
        DocumentType,
        name="document_type",
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Reservation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reservations"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (CheckConstraint("check_out > check_in", name="valid_stay"),)

    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_out: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    room_id: Mapped[UUID] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), index=True)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    rate_id: Mapped[UUID] = mapped_column(
        ForeignKey("room_rates.id", ondelete="RESTRICT"), index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(document_type_column())
    document_number: Mapped[str | None] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[date]
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(254))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        default=ReservationStatus.BOOKED,
        server_default=ReservationStatus.BOOKED.value,
        index=True,
    )
    country_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_countries.code", ondelete="RESTRICT")
    )
    city: Mapped[str] = mapped_column(String(150))
    region: Mapped[str] = mapped_column(String(150))
    district: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(500))
    travel_reason: Mapped[str] = mapped_column(String(255))
    dietary_restrictions: Mapped[str] = mapped_column(String(500))
    gender: Mapped[str] = mapped_column(String(50))
    payment_method_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="RESTRICT"), index=True
    )
    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    transaction_number: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(2000))
    company_name: Mapped[str | None] = mapped_column(String(255))
    ruc: Mapped[str | None] = mapped_column(String(11))
    discount_code: Mapped[str | None] = mapped_column(String(100))

    room: Mapped[Room] = relationship(lazy="raise")
    rate: Mapped[Rate] = relationship(lazy="raise")
    companions: Mapped[list["Companion"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", order_by="Companion.created_at, Companion.id"
    )
    detail: Mapped["ReservationDetail | None"] = relationship(
        cascade="all, delete-orphan", lazy="raise"
    )

    @property
    def room_name(self) -> str:
        return self.room.name

    @property
    def room_type_name(self) -> str:
        return self.room.room_type.name

    @property
    def rate_name(self) -> str:
        return self.rate.name


class Companion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reservation_companions"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(document_type_column())
    document_number: Mapped[str] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(255))
    gender: Mapped[PersonGender | None] = mapped_column(text_choices(PersonGender, "gender"))
    birth_date: Mapped[date | None]
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(254))


class ReservationDetail(TimestampMixin, Base):
    __tablename__ = "reservation_details"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        CheckConstraint(
            "amount_paid >= 0 AND amount_remaining >= 0 AND "
            "round(amount_paid + amount_remaining - final_total, 2) = 0",
            name="valid_balance",
        ),
        CheckConstraint("stay_days >= 1", name="positive_stay_days"),
    )

    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), primary_key=True
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    promotion_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    final_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    customer_document_number: Mapped[str | None] = mapped_column(String(32))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_phone: Mapped[str | None] = mapped_column(String(32))
    customer_email: Mapped[str | None] = mapped_column(String(254))
    room_name: Mapped[str | None] = mapped_column(String(150))
    stay_days: Mapped[int]
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class ReservationDiscountCode(TimestampMixin, Base):
    __tablename__ = "reservation_discount_codes"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="valid_dates"),
        CheckConstraint(
            "discount_percentage > 0 AND discount_percentage <= 100", name="valid_percentage"
        ),
        CheckConstraint(
            "NOT is_active OR (room_type_id IS NOT NULL AND start_date IS NOT NULL "
            "AND end_date IS NOT NULL AND discount_percentage IS NOT NULL)",
            name="active_requires_configuration",
        ),
    )

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    id: Mapped[UUID] = mapped_column(
        unique=True, default=uuid4, server_default=func.gen_random_uuid()
    )
    room_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("room_types.id", ondelete="RESTRICT"), index=True
    )
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    discount_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class ReservationQuote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reservation_quotes"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        CheckConstraint("check_out > check_in", name="valid_stay"),
        CheckConstraint("quoted_total >= 0", name="nonnegative_total"),
    )

    room_id: Mapped[UUID] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"))
    rate_id: Mapped[UUID] = mapped_column(ForeignKey("room_rates.id", ondelete="RESTRICT"))
    reservation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="RESTRICT"), index=True
    )
    check_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_out: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quoted_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReservationPayment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reservation_payments"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (CheckConstraint("amount > 0", name="positive_amount"),)

    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), index=True
    )
    payment_method_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="RESTRICT")
    )
    culqi_charge_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("culqi_charges.id", ondelete="RESTRICT"), unique=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

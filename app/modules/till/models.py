from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Direction(StrEnum):
    INCOME = "INGRESO"
    EXPENSE = "EGRESO"


class Till(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tills"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    name: Mapped[str] = mapped_column(String(150), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class TillConcept(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "till_concepts"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class TillShift(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "till_shifts"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        Index(
            "uq_till_shifts_open_till",
            "till_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
            sqlite_where=text("closed_at IS NULL"),
        ),
        CheckConstraint("opening_amount >= 0", name="nonnegative_opening_amount"),
        CheckConstraint("counted_cash >= 0", name="nonnegative_counted_cash"),
    )

    till_id: Mapped[UUID] = mapped_column(ForeignKey("tills.id", ondelete="RESTRICT"), index=True)
    opened_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    closed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class TillMovement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "till_movements"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        UniqueConstraint("transfer_id", "direction"),
    )

    shift_id: Mapped[UUID] = mapped_column(
        ForeignKey("till_shifts.id", ondelete="RESTRICT"), index=True
    )
    concept_id: Mapped[UUID] = mapped_column(ForeignKey("till_concepts.id", ondelete="RESTRICT"))
    payment_method_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="RESTRICT")
    )
    registered_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    direction: Mapped[Direction] = mapped_column(
        Enum(
            Direction,
            name="direction",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda choices: [choice.value for choice in choices],
        )
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(String(500))
    reservation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="RESTRICT"), index=True
    )
    stay_id: Mapped[UUID | None]
    consumption_id: Mapped[UUID | None]
    charge_id: Mapped[str | None] = mapped_column(String(150), index=True)
    transfer_id: Mapped[UUID | None]
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    void_reason: Mapped[str | None] = mapped_column(String(500))


class TillOperation(TimestampMixin, Base):
    __tablename__ = "till_operations"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSON)

from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

PROCESSING = "PROCESSING"
SUCCEEDED = "SUCCEEDED"
DECLINED = "DECLINED"
REQUIRES_3DS = "REQUIRES_3DS"


class CulqiCharge(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "culqi_charges"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "status IN ('PROCESSING', 'SUCCEEDED', 'DECLINED', 'REQUIRES_3DS')",
            name="valid_status",
        ),
        Index(
            "uq_culqi_charges_processing_reservation",
            "reservation_id",
            unique=True,
            postgresql_where=text("status = 'PROCESSING'"),
            sqlite_where=text("status = 'PROCESSING'"),
        ),
    )

    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("reservations.id", ondelete="RESTRICT"), index=True
    )
    payment_method_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20))
    provider_charge_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    device_id: Mapped[UUID | None]

from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
    Table,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

from .choices import RoomStatus


class RoomType(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "room_types"
    __table_args__ = (CheckConstraint("bed_places >= 1", name="positive_bed_places"),)
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    name: Mapped[str] = mapped_column(String(150), unique=True)
    has_bathroom: Mapped[bool | None]
    bed_places: Mapped[int | None]


class Rate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "room_rates"
    __table_args__ = (CheckConstraint("price >= 0", name="nonnegative_price"),)
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    name: Mapped[str] = mapped_column(String(150))
    rate_condition: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class RoomCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "room_categories"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    name: Mapped[str] = mapped_column(String(150), unique=True)


class Floor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "room_floors"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    description: Mapped[str] = mapped_column(String(150), unique=True)


room_rate_links = Table(
    "room_rate_links",
    Base.metadata,
    Column("room_id", ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "rate_id", ForeignKey("room_rates.id", ondelete="RESTRICT"), primary_key=True, index=True
    ),
)


class Room(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rooms"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    name: Mapped[str] = mapped_column(String(150))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[RoomStatus] = mapped_column(
        Enum(
            RoomStatus,
            name="status",
            values_callable=lambda members: [member.value for member in members],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=50,
        ),
        default=RoomStatus.AVAILABLE,
        server_default=RoomStatus.AVAILABLE.value,
    )
    visible: Mapped[bool] = mapped_column(default=True, server_default=true())
    room_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("room_types.id", ondelete="RESTRICT"), index=True
    )
    room_type: Mapped[RoomType] = relationship(lazy="raise")
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("room_categories.id", ondelete="RESTRICT"), index=True
    )
    floor_id: Mapped[UUID] = mapped_column(
        ForeignKey("room_floors.id", ondelete="RESTRICT"), index=True
    )
    details: Mapped[list[dict[str, str | None]]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    rates: Mapped[list[Rate]] = relationship(
        secondary=room_rate_links, lazy="raise", order_by=Rate.id
    )
    images: Mapped[list["RoomImage"]] = relationship(
        lazy="raise", order_by="RoomImage.created_at, RoomImage.id", passive_deletes="all"
    )

    @property
    def rate_ids(self) -> list[UUID]:
        return [rate.id for rate in self.rates]


class RoomImage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "room_images"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    room_id: Mapped[UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    content_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)

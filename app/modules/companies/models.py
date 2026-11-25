from typing import ClassVar
from uuid import UUID

from sqlalchemy import ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.ubigee.models import District


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    ruc: Mapped[str] = mapped_column(String(11), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    lodging_class: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))
    certificate_number: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(32))
    coordinate_system: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(2048))
    reservations_email: Mapped[str | None] = mapped_column(String(254))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    national_hotel_chain: Mapped[bool] = mapped_column(default=False, server_default=false())
    international_hotel_chain: Mapped[bool] = mapped_column(default=False, server_default=false())
    district_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_districts.code", ondelete="RESTRICT"), index=True
    )
    district: Mapped[District] = relationship(lazy="raise")


class Branch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_branches"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    logo: Mapped[str | None] = mapped_column(String(2048))
    logo_ticket: Mapped[str | None] = mapped_column(String(2048))
    district_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_districts.code", ondelete="RESTRICT"), index=True
    )
    district: Mapped[District] = relationship(lazy="raise")

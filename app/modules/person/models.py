from enum import StrEnum
from typing import ClassVar

from sqlalchemy import Boolean, Enum, ForeignKey, String, false, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.document_types import DocumentType
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

from .choices import PersonArea, PersonCategory, PersonGender


def text_choices(enum: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class Person(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "persons"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[DocumentType] = mapped_column(text_choices(DocumentType, "document_type"))
    document_number: Mapped[str | None] = mapped_column(String(32))
    mobile_phone: Mapped[str] = mapped_column(String(32))
    area: Mapped[PersonArea] = mapped_column(text_choices(PersonArea, "area"))
    gender: Mapped[PersonGender] = mapped_column(text_choices(PersonGender, "gender"))
    category: Mapped[PersonCategory] = mapped_column(text_choices(PersonCategory, "category"))
    is_permanent_employee: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __uppercase_display_fields__ = False

    identity_key: Mapped[str] = mapped_column(String(320), unique=True)
    document_type: Mapped[DocumentType] = mapped_column(text_choices(DocumentType, "document_type"))
    document_number: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(254))
    country_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_countries.code", ondelete="RESTRICT")
    )
    reservation_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    city: Mapped[str] = mapped_column(String(150))
    district_code: Mapped[str | None] = mapped_column(
        ForeignKey("ubigeo_districts.code", ondelete="RESTRICT")
    )
    address: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

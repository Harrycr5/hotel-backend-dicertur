from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, Numeric, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.document_types import DocumentType
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.person.models import text_choices

from .choices import ComplaintType, MediaType, WebsiteCategory


class WebsiteMedia(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "website_media"
    __uppercase_display_fields__ = False

    kind: Mapped[MediaType] = mapped_column(text_choices(MediaType, "kind"))
    title: Mapped[str] = mapped_column(String(150))
    content_type: Mapped[str] = mapped_column(String(32))
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)


class WebsiteGallery(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "website_galleries"
    __uppercase_display_fields__ = False

    category: Mapped[WebsiteCategory] = mapped_column(text_choices(WebsiteCategory, "category"))
    description: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    images: Mapped[list["WebsiteGalleryImage"]] = relationship(
        lazy="raise",
        passive_deletes="all",
        order_by="WebsiteGalleryImage.created_at, WebsiteGalleryImage.id",
    )


class WebsiteGalleryImage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "website_gallery_images"

    gallery_id: Mapped[UUID] = mapped_column(
        ForeignKey("website_galleries.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)


class WebsiteDescription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "website_descriptions"
    __uppercase_display_fields__ = False

    category: Mapped[WebsiteCategory] = mapped_column(
        text_choices(WebsiteCategory, "category"), unique=True
    )
    description: Mapped[str] = mapped_column(Text)


class WebsiteComplaint(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "website_complaints"
    __uppercase_display_fields__ = False
    __table_args__ = (CheckConstraint("amount >= 0", name="nonnegative_amount"),)

    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(254))
    mobile_phone: Mapped[str | None] = mapped_column(String(32))
    document_type: Mapped[DocumentType] = mapped_column(text_choices(DocumentType, "document_type"))
    document_number: Mapped[str] = mapped_column(String(32))
    request_type: Mapped[ComplaintType] = mapped_column(text_choices(ComplaintType, "request_type"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    detail: Mapped[str] = mapped_column(Text)
    expected_solution: Mapped[str] = mapped_column(Text)


class WebsiteContact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "website_contacts"
    __uppercase_display_fields__ = False

    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)

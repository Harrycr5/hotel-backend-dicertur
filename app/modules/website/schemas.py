from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.core.document_types import DocumentType
from app.core.phone_numbers import MobileNumber

from .choices import ComplaintType, MediaType, WebsiteCategory

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
GalleryDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class VideoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    video: str


class PDFCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    pdf: str


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: MediaType
    title: str
    created_at: datetime
    url: str


class GalleryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: WebsiteCategory
    description: GalleryDescription
    is_active: bool = True


class GalleryImageRead(BaseModel):
    id: UUID
    image: str


class GalleryRead(GalleryCreate):
    id: UUID
    created_at: datetime
    images: list[GalleryImageRead]


class DescriptionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Message


class DescriptionRead(DescriptionWrite):
    model_config = ConfigDict(from_attributes=True)

    category: WebsiteCategory


class ComplaintCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    email: EmailStr
    mobile_phone: MobileNumber
    document_type: DocumentType
    document_number: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
    ]
    request_type: ComplaintType
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    detail: Message
    expected_solution: Message


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Title
    email: EmailStr
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    message: Message


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class ComplaintRead(ComplaintCreate, SubmissionRead):
    mobile_phone: str | None


class ContactRead(ContactCreate, SubmissionRead):
    pass


class WebsiteChoice(BaseModel):
    value: str
    label: str


class WebsiteChoicesRead(BaseModel):
    categories: list[WebsiteChoice]
    document_types: list[WebsiteChoice]
    request_types: list[WebsiteChoice]

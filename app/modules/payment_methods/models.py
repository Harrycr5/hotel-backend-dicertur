from typing import ClassVar

from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class PaymentMethod(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payment_methods"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Country(Base):
    __tablename__ = "ubigeo_countries"
    __permission_actions__ = ()

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Department(Base):
    __tablename__ = "ubigeo_departments"
    __permission_actions__ = ()

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_countries.code", ondelete="RESTRICT"), index=True
    )


class Province(Base):
    __tablename__ = "ubigeo_provinces"
    __permission_actions__ = ()

    code: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_departments.code", ondelete="RESTRICT"), index=True
    )
    department: Mapped[Department] = relationship(lazy="raise")


class District(Base):
    __tablename__ = "ubigeo_districts"
    __permission_actions__ = ()

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    province_code: Mapped[str] = mapped_column(
        ForeignKey("ubigeo_provinces.code", ondelete="RESTRICT"), index=True
    )
    province: Mapped[Province] = relationship(lazy="raise")

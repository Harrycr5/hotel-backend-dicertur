"""Create and populate the ubigeo catalog.

Revision ID: 6c2cc6e7d991
Revises: e3b426c8ad51
"""

import sqlalchemy as sa
from alembic import op

from app.modules.ubigee.catalog import catalog_rows

revision = "6c2cc6e7d991"
down_revision = "e3b426c8ad51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    countries, departments, provinces, districts = catalog_rows()
    country_table = op.create_table(
        "ubigeo_countries",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
    )
    department_table = op.create_table(
        "ubigeo_departments",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "country_code",
            sa.String(2),
            sa.ForeignKey("ubigeo_countries.code", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    province_table = op.create_table(
        "ubigeo_provinces",
        sa.Column("code", sa.String(4), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "department_code",
            sa.String(2),
            sa.ForeignKey("ubigeo_departments.code", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    district_table = op.create_table(
        "ubigeo_districts",
        sa.Column("code", sa.String(6), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "province_code",
            sa.String(4),
            sa.ForeignKey("ubigeo_provinces.code", ondelete="RESTRICT"),
            nullable=False,
        ),
    )

    op.bulk_insert(country_table, countries)
    op.bulk_insert(department_table, departments)
    op.bulk_insert(province_table, provinces)
    op.bulk_insert(district_table, districts)

    op.create_index("ix_ubigeo_departments_country_code", "ubigeo_departments", ["country_code"])
    op.create_index("ix_ubigeo_provinces_department_code", "ubigeo_provinces", ["department_code"])
    op.create_index("ix_ubigeo_districts_province_code", "ubigeo_districts", ["province_code"])


def downgrade() -> None:
    op.drop_table("ubigeo_districts")
    op.drop_table("ubigeo_provinces")
    op.drop_table("ubigeo_departments")
    op.drop_table("ubigeo_countries")

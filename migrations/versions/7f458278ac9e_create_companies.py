"""Create companies and company branches."""

import sqlalchemy as sa
from alembic import op

revision = "7f458278ac9e"
down_revision = "1d76eb56a3fc"
branch_labels = None
depends_on = None


def base_columns():
    return (
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "district_code",
            sa.String(6),
            sa.ForeignKey("ubigeo_districts.code", ondelete="RESTRICT"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "companies",
        *base_columns(),
        sa.Column("ruc", sa.String(11), nullable=False, unique=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255)),
        sa.Column("lodging_class", sa.String(100)),
        sa.Column("category", sa.String(100)),
        sa.Column("certificate_number", sa.String(100)),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("coordinate_system", sa.String(100)),
        sa.Column("website", sa.String(2048)),
        sa.Column("reservations_email", sa.String(254)),
        sa.Column("contact_name", sa.String(255)),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("contact_email", sa.String(254)),
        sa.Column("national_hotel_chain", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "international_hotel_chain", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.create_table(
        "company_branches",
        *base_columns(),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255)),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(32)),
        sa.Column("logo", sa.String(2048)),
        sa.Column("logo_ticket", sa.String(2048)),
    )
    op.create_index("ix_companies_district_code", "companies", ["district_code"])
    op.create_index("ix_company_branches_district_code", "company_branches", ["district_code"])
    op.create_index("ix_company_branches_company_id", "company_branches", ["company_id"])


def downgrade() -> None:
    op.drop_table("company_branches")
    op.drop_table("companies")

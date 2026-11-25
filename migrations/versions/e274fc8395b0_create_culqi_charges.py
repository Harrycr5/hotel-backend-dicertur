"""Persist Culqi charge attempts before dispatch."""

import sqlalchemy as sa
from alembic import op

revision = "e274fc8395b0"
down_revision = "8a4df09c721e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "culqi_charges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            sa.ForeignKey("reservations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "payment_method_id",
            sa.Uuid(),
            sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_charge_id", sa.String(100), unique=True),
        sa.Column("device_id", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'SUCCEEDED', 'DECLINED', 'REQUIRES_3DS')",
            name="valid_status",
        ),
    )
    op.create_index("ix_culqi_charges_reservation_id", "culqi_charges", ["reservation_id"])
    op.create_index(
        "uq_culqi_charges_processing_reservation",
        "culqi_charges",
        ["reservation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PROCESSING'"),
    )


def downgrade() -> None:
    op.drop_table("culqi_charges")

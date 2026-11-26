"""Add configuration to reservation discount codes."""

import sqlalchemy as sa
from alembic import op

revision = "0d95be68c3a1"
down_revision = "ed834a961b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "reservation_discount_codes"
    op.add_column(
        table, sa.Column("id", sa.Uuid(), server_default=sa.func.gen_random_uuid(), nullable=False)
    )
    op.create_unique_constraint("uq_reservation_discount_codes_id", table, ["id"])
    op.add_column(
        table,
        sa.Column("room_type_id", sa.Uuid(), sa.ForeignKey("room_types.id", ondelete="RESTRICT")),
    )
    op.create_index("ix_reservation_discount_codes_room_type_id", table, ["room_type_id"])
    op.add_column(table, sa.Column("start_date", sa.Date()))
    op.add_column(table, sa.Column("end_date", sa.Date()))
    op.add_column(table, sa.Column("discount_percentage", sa.Numeric(5, 2)))
    op.add_column(
        table, sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.alter_column(table, "is_active", server_default=sa.true())
    op.create_check_constraint("valid_dates", table, "end_date >= start_date")
    op.create_check_constraint(
        "valid_percentage", table, "discount_percentage > 0 AND discount_percentage <= 100"
    )
    op.create_check_constraint(
        "active_requires_configuration",
        table,
        "NOT is_active OR (room_type_id IS NOT NULL AND start_date IS NOT NULL "
        "AND end_date IS NOT NULL AND discount_percentage IS NOT NULL)",
    )


def downgrade() -> None:
    table = "reservation_discount_codes"
    for name in ("active_requires_configuration", "valid_percentage", "valid_dates"):
        op.drop_constraint(name, table, type_="check")
    op.drop_index("ix_reservation_discount_codes_room_type_id", table_name=table)
    op.drop_constraint("uq_reservation_discount_codes_id", table, type_="unique")
    for column in (
        "is_active",
        "discount_percentage",
        "end_date",
        "start_date",
        "room_type_id",
        "id",
    ):
        op.drop_column(table, column)

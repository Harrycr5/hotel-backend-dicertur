"""Add companion gender and reservation quotes."""

import sqlalchemy as sa
from alembic import op

revision = "41c39f2e887a"
down_revision = "2b25d38d348a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reservation_companions", sa.Column("gender", sa.String(9)))
    op.create_check_constraint(
        "gender", "reservation_companions", "gender IN ('MASCULINO', 'FEMENINO')"
    )
    op.create_table(
        "reservation_quotes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "room_id", sa.Uuid(), sa.ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "rate_id",
            sa.Uuid(),
            sa.ForeignKey("room_rates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reservation_id", sa.Uuid(), sa.ForeignKey("reservations.id", ondelete="RESTRICT")
        ),
        sa.Column("check_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_out", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quoted_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("check_out > check_in", name="valid_stay"),
        sa.CheckConstraint("quoted_total >= 0", name="nonnegative_total"),
    )
    op.create_index(
        "ix_reservation_quotes_reservation_id", "reservation_quotes", ["reservation_id"]
    )


def downgrade() -> None:
    op.drop_table("reservation_quotes")
    op.drop_constraint("gender", "reservation_companions", type_="check")
    op.drop_column("reservation_companions", "gender")

"""Track the payment methods used for reservation payments."""

import sqlalchemy as sa
from alembic import op

revision = "70db419e12c3"
down_revision = "e274fc8395b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservation_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            sa.ForeignKey("reservations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_method_id",
            sa.Uuid(),
            sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "culqi_charge_id",
            sa.Uuid(),
            sa.ForeignKey("culqi_charges.id", ondelete="RESTRICT"),
            unique=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
    )
    op.create_index(
        "ix_reservation_payments_reservation_id", "reservation_payments", ["reservation_id"]
    )
    op.execute(
        """
        INSERT INTO reservation_payments (
            id, reservation_id, payment_method_id, culqi_charge_id, amount, created_at
        )
        SELECT gen_random_uuid(), reservation_id, payment_method_id, id, amount, updated_at
        FROM culqi_charges
        WHERE status = 'SUCCEEDED'
        """
    )


def downgrade() -> None:
    op.drop_table("reservation_payments")

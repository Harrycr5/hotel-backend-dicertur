"""Store discount codes issued for reservations."""

import sqlalchemy as sa
from alembic import op

revision = "ed834a961b20"
down_revision = "4fe92b815103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservation_discount_codes",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("reservation_discount_codes")

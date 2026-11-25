"""Add permanent employee status to persons."""

import sqlalchemy as sa
from alembic import op

revision = "1d76eb56a3fc"
down_revision = "c4f9db76307e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column("is_permanent_employee", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("persons", "is_permanent_employee")

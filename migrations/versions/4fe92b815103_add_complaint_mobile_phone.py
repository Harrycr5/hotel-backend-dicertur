"""Add a mobile number to website complaints."""

import sqlalchemy as sa
from alembic import op

revision = "4fe92b815103"
down_revision = "e83ac17d2b54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("website_complaints", sa.Column("mobile_phone", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("website_complaints", "mobile_phone")

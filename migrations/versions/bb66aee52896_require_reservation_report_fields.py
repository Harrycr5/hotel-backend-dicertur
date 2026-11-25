"""Require guest and rate information needed for reservation reporting."""

from alembic import op

revision = "bb66aee52896"
down_revision = "7bb89ee312ac"
branch_labels = None
depends_on = None

REQUIRED_COLUMNS = (
    "rate_id",
    "birth_date",
    "phone",
    "email",
    "country_code",
    "city",
    "region",
    "district",
    "address",
    "travel_reason",
    "dietary_restrictions",
    "gender",
)


def upgrade() -> None:
    for column in REQUIRED_COLUMNS:
        op.alter_column("reservations", column, nullable=False)


def downgrade() -> None:
    for column in REQUIRED_COLUMNS:
        op.alter_column("reservations", column, nullable=True)

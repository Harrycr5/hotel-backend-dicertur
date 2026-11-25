"""Create room types and rates, and seed the initial room types."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "34aa51c993b7"
down_revision = "7f458278ac9e"
branch_labels = None
depends_on = None

ROOM_TYPES = (
    (UUID("fa606012-6c6d-44a1-81ac-111ae6efa005"), "Individuales o simples"),
    (UUID("bef56580-8d24-43b7-9485-78ad2fc8b107"), "Dobles y matrimoniales"),
    (UUID("c1a714f3-1cde-4b63-b9b1-800470a04460"), "Suites (incluye sala)"),
    (UUID("d7372e40-e2ea-4b8d-a6cf-af6aa84567d1"), "Triples"),
    (UUID("a083ecde-6459-4b39-93c8-f03bbe1fa99e"), "Bungalós (casas pequeñas)"),
)


def base_columns():
    return (
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    room_types = op.create_table(
        "room_types",
        *base_columns(),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("has_bathroom", sa.Boolean()),
        sa.Column("bed_places", sa.Integer()),
        sa.CheckConstraint("bed_places >= 1", name="positive_bed_places"),
    )
    op.bulk_insert(room_types, [{"id": room_id, "name": name} for room_id, name in ROOM_TYPES])

    op.create_table(
        "room_rates",
        *base_columns(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("rate_condition", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("price >= 0", name="nonnegative_price"),
    )


def downgrade() -> None:
    op.drop_table("room_rates")
    op.drop_table("room_types")

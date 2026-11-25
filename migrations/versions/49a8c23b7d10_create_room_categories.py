"""Create the room category catalog and associate it with rooms."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "49a8c23b7d10"
down_revision = "ab4509f27406"
branch_labels = None
depends_on = None


def upgrade() -> None:
    categories = op.create_table(
        "room_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.bulk_insert(
        categories,
        [
            {"id": UUID("93044be2-166c-454c-82e0-0f491d4eb246"), "name": "Estándar"},
            {"id": UUID("216510a1-f080-4770-8806-38f949098342"), "name": "Superior"},
            {"id": UUID("958202c0-da5b-4434-ac84-e8fff1f3cc38"), "name": "Premium"},
        ],
    )
    op.add_column(
        "rooms",
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("room_categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_rooms_category_id", "rooms", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_rooms_category_id", table_name="rooms")
    op.drop_column("rooms", "category_id")
    op.drop_table("room_categories")

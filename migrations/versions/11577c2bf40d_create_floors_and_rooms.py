"""Create floors, rooms, room images and room-rate associations."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "11577c2bf40d"
down_revision = "34aa51c993b7"
branch_labels = None
depends_on = None


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
    floors = op.create_table(
        "room_floors",
        *base_columns(),
        sa.Column("description", sa.String(150), nullable=False, unique=True),
    )
    op.bulk_insert(
        floors,
        [
            {"id": UUID(f"c17575b6-f19c-453a-a4d4-2d8b8066920{number}"), "description": description}
            for number, description in enumerate(
                ("Primer piso", "Segundo piso", "Tercer piso", "Cuarto piso", "Quinto piso"), 1
            )
        ],
    )
    op.create_table(
        "rooms",
        *base_columns(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(2000)),
        sa.Column("status", sa.String(50), nullable=False, server_default="DISPONIBLE"),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "room_type_id",
            sa.Uuid(),
            sa.ForeignKey("room_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "floor_id",
            sa.Uuid(),
            sa.ForeignKey("room_floors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("details", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "room_rate_links",
        sa.Column(
            "room_id", sa.Uuid(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "rate_id",
            sa.Uuid(),
            sa.ForeignKey("room_rates.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    op.create_table(
        "room_images",
        *base_columns(),
        sa.Column(
            "room_id", sa.Uuid(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_rooms_room_type_id", "rooms", ["room_type_id"])
    op.create_index("ix_rooms_floor_id", "rooms", ["floor_id"])
    op.create_index("ix_room_rate_links_rate_id", "room_rate_links", ["rate_id"])
    op.create_index("ix_room_images_room_id", "room_images", ["room_id"])


def downgrade() -> None:
    op.drop_table("room_images")
    op.drop_table("room_rate_links")
    op.drop_table("rooms")
    op.drop_table("room_floors")

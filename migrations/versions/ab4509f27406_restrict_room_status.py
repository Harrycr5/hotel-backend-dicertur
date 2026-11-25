"""Restrict room status to the supported choices."""

import sqlalchemy as sa
from alembic import op

revision = "ab4509f27406"
down_revision = "11577c2bf40d"
branch_labels = None
depends_on = None

STATUSES = ("DISPONIBLE", "OCUPADO", "MANTENIMIENTO", "RESERVADO")


def upgrade() -> None:
    rooms = sa.table("rooms", sa.column("status", sa.String(50)))
    normalized_status = sa.func.upper(sa.func.trim(rooms.c.status))
    op.execute(
        rooms.update()
        .where(normalized_status.in_(STATUSES), rooms.c.status != normalized_status)
        .values(status=normalized_status)
    )
    op.create_check_constraint("status", "rooms", rooms.c.status.in_(STATUSES))


def downgrade() -> None:
    op.drop_constraint("status", "rooms", type_="check")

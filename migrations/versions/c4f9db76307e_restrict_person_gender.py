"""Restrict person gender to the supported choices."""

import sqlalchemy as sa
from alembic import op

revision = "c4f9db76307e"
down_revision = "af21bde63c48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    persons = sa.table("persons", sa.column("gender", sa.String(50)))
    normalized_gender = sa.func.upper(sa.func.trim(persons.c.gender))
    op.execute(
        persons.update()
        .where(normalized_gender.in_(("MASCULINO", "FEMENINO")))
        .where(persons.c.gender != normalized_gender)
        .values(gender=normalized_gender)
    )
    op.create_check_constraint("gender", "persons", persons.c.gender.in_(("MASCULINO", "FEMENINO")))
    op.alter_column("persons", "gender", existing_type=sa.String(50), type_=sa.String(9))


def downgrade() -> None:
    op.drop_constraint("gender", "persons", type_="check")
    op.alter_column("persons", "gender", existing_type=sa.String(9), type_=sa.String(50))

"""Track employment dates, branches and assignment history."""

import sqlalchemy as sa
from alembic import op

revision = "71b27dc9e804"
down_revision = "41c39f2e887a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("employment_start_date", sa.Date()))
    op.add_column("persons", sa.Column("employment_end_date", sa.Date()))
    op.add_column(
        "persons",
        sa.Column(
            "branch_id", sa.Uuid(), sa.ForeignKey("company_branches.id", ondelete="RESTRICT")
        ),
    )
    op.create_index("ix_persons_branch_id", "persons", ["branch_id"])
    op.create_check_constraint(
        "valid_employment_dates", "persons", "employment_end_date >= employment_start_date"
    )
    op.create_table(
        "person_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "person_id", sa.Uuid(), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "branch_id", sa.Uuid(), sa.ForeignKey("company_branches.id", ondelete="RESTRICT")
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "area",
            sa.Enum(
                "EJECUTIVOS Y ADMINISTRATIVOS",
                "RECEPCIÓN",
                "CONSERJERÍA",
                "LIMPIEZA",
                "COMEDOR Y CAFETERÍA",
                "BAR",
                "DEMÁS PUESTOS",
                name="area",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "EMPLEADO",
                "PROPIETARIO O SOCIO",
                "NO REMUNERADO",
                name="category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("is_permanent_employee", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("person_id", "effective_from"),
    )
    op.create_index("ix_person_assignments_branch_id", "person_assignments", ["branch_id"])
    op.execute(
        """
        INSERT INTO person_assignments (
            id, person_id, branch_id, effective_from, area, category, is_permanent_employee
        )
        SELECT gen_random_uuid(), id, branch_id, (created_at AT TIME ZONE 'America/Lima')::date,
            area, category, is_permanent_employee
        FROM persons
        """
    )


def downgrade() -> None:
    op.drop_table("person_assignments")
    op.drop_constraint("valid_employment_dates", "persons", type_="check")
    op.drop_index("ix_persons_branch_id", table_name="persons")
    op.drop_column("persons", "branch_id")
    op.drop_column("persons", "employment_end_date")
    op.drop_column("persons", "employment_start_date")

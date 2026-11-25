"""Create persons."""

import sqlalchemy as sa
from alembic import op

revision = "af21bde63c48"
down_revision = "6c2cc6e7d991"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "SIN DOCUMENTO",
                "DNI",
                "RUC",
                "CARNET DE EXTRANJERIA",
                "PASAPORTE",
                name="document_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("document_number", sa.String(32), nullable=True),
        sa.Column("mobile_phone", sa.String(32), nullable=False),
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
        sa.Column("gender", sa.String(50), nullable=False),
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
    )


def downgrade() -> None:
    op.drop_table("persons")

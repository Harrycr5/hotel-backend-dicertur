"""Create cash tills, shifts, audited movements and idempotency records."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision = "8a4df09c721e"
down_revision = "5e423db988a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tills",
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tills")),
        sa.UniqueConstraint("name", name=op.f("uq_tills_name")),
    )
    op.create_table(
        "till_concepts",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_concepts")),
        sa.UniqueConstraint("code", name=op.f("uq_till_concepts_code")),
    )
    op.create_table(
        "till_shifts",
        sa.Column("till_id", sa.Uuid(), nullable=False),
        sa.Column("opened_by_id", sa.Uuid(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("closed_by_id", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_cash", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("counted_cash", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("difference", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "counted_cash >= 0", name=op.f("ck_till_shifts_nonnegative_counted_cash")
        ),
        sa.CheckConstraint(
            "opening_amount >= 0", name=op.f("ck_till_shifts_nonnegative_opening_amount")
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_id"],
            ["users.id"],
            name=op.f("fk_till_shifts_closed_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by_id"],
            ["users.id"],
            name=op.f("fk_till_shifts_opened_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["till_id"],
            ["tills.id"],
            name=op.f("fk_till_shifts_till_id_tills"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_shifts")),
    )
    op.create_index(op.f("ix_till_shifts_till_id"), "till_shifts", ["till_id"], unique=False)
    op.create_index(
        "uq_till_shifts_open_till",
        "till_shifts",
        ["till_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "till_movements",
        sa.Column("shift_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("payment_method_id", sa.Uuid(), nullable=False),
        sa.Column("registered_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "direction",
            sa.Enum(
                "INGRESO", "EGRESO", name="direction", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("stay_id", sa.Uuid(), nullable=True),
        sa.Column("consumption_id", sa.Uuid(), nullable=True),
        sa.Column("charge_id", sa.String(length=150), nullable=True),
        sa.Column("transfer_id", sa.Uuid(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_id", sa.Uuid(), nullable=True),
        sa.Column("void_reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_till_movements_positive_amount")),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["till_concepts.id"],
            name=op.f("fk_till_movements_concept_id_till_concepts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_method_id"],
            ["payment_methods.id"],
            name=op.f("fk_till_movements_payment_method_id_payment_methods"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["registered_by_id"],
            ["users.id"],
            name=op.f("fk_till_movements_registered_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
            name=op.f("fk_till_movements_reservation_id_reservations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["till_shifts.id"],
            name=op.f("fk_till_movements_shift_id_till_shifts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voided_by_id"],
            ["users.id"],
            name=op.f("fk_till_movements_voided_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_movements")),
        sa.UniqueConstraint("transfer_id", "direction", name=op.f("uq_till_movements_transfer_id")),
    )
    op.create_index(
        op.f("ix_till_movements_charge_id"), "till_movements", ["charge_id"], unique=False
    )
    op.create_index(
        op.f("ix_till_movements_reservation_id"), "till_movements", ["reservation_id"], unique=False
    )
    op.create_index(
        op.f("ix_till_movements_shift_id"), "till_movements", ["shift_id"], unique=False
    )
    op.create_table(
        "till_operations",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_till_operations_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_till_operations")),
    )

    concepts = sa.table(
        "till_concepts",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        concepts,
        [
            {"id": UUID(f"9a29ea8d-258d-401d-b9c7-b6c3b244d06{index}"), "code": code, "name": name}
            for index, (code, name) in enumerate(
                (
                    ("PAGO_RESERVA", "Pago de reserva"),
                    ("CONSUMO_BAR", "Consumo de bar"),
                    ("COMPRA_INSUMOS", "Compra de insumos"),
                    ("DEVOLUCION", "Devolución"),
                    ("TRANSFERENCIA_ENTRE_CAJAS", "Transferencia entre cajas"),
                ),
                1,
            )
        ],
    )
    methods = sa.table(
        "payment_methods",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.execute(
        insert(methods)
        .values(id=UUID("9a29ea8d-258d-401d-b9c7-b6c3b244d066"), code="YAPE", name="Yape")
        .on_conflict_do_nothing(index_elements=[methods.c.code])
    )


def downgrade() -> None:
    # Yape can be referenced by other modules once added to the shared catalog.
    op.drop_table("till_operations")
    op.drop_table("till_movements")
    op.drop_table("till_shifts")
    op.drop_table("till_concepts")
    op.drop_table("tills")

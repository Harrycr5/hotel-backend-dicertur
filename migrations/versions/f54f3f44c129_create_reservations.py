"""Create reservations, companions, reservation details and payment methods."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "f54f3f44c129"
down_revision = "49a8c23b7d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_methods")),
        sa.UniqueConstraint("code", name=op.f("uq_payment_methods_code")),
    )
    op.create_table(
        "reservations",
        sa.Column("check_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_out", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("rate_id", sa.Uuid(), nullable=True),
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
        sa.Column("document_number", sa.String(length=32), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "CONFIRMADO",
                "RESERVADO",
                "CANCELADO",
                "CADUCADO",
                "RESERVA SIN PAGOS",
                "RESERVA CON PAGOS PARCIALES",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="RESERVADO",
            nullable=False,
        ),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=150), nullable=True),
        sa.Column("region", sa.String(length=150), nullable=True),
        sa.Column("district", sa.String(length=150), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("travel_reason", sa.String(length=255), nullable=True),
        sa.Column("dietary_restrictions", sa.String(length=500), nullable=True),
        sa.Column("gender", sa.String(length=50), nullable=True),
        sa.Column("payment_method_id", sa.Uuid(), nullable=True),
        sa.Column("payment_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("transaction_number", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("ruc", sa.String(length=11), nullable=True),
        sa.Column("discount_code", sa.String(length=100), nullable=True),
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
        sa.CheckConstraint("check_out > check_in", name=op.f("ck_reservations_valid_stay")),
        sa.ForeignKeyConstraint(
            ["country_code"],
            ["ubigeo_countries.code"],
            name=op.f("fk_reservations_country_code_ubigeo_countries"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_method_id"],
            ["payment_methods.id"],
            name=op.f("fk_reservations_payment_method_id_payment_methods"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rate_id"],
            ["room_rates.id"],
            name=op.f("fk_reservations_rate_id_room_rates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name=op.f("fk_reservations_room_id_rooms"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservations")),
    )
    op.create_index(
        op.f("ix_reservations_payment_method_id"),
        "reservations",
        ["payment_method_id"],
        unique=False,
    )
    op.create_index(op.f("ix_reservations_rate_id"), "reservations", ["rate_id"], unique=False)
    op.create_index(op.f("ix_reservations_room_id"), "reservations", ["room_id"], unique=False)
    op.create_index(op.f("ix_reservations_status"), "reservations", ["status"], unique=False)
    op.create_table(
        "reservation_companions",
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
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
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
            name=op.f("fk_reservation_companions_reservation_id_reservations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservation_companions")),
    )
    op.create_index(
        op.f("ix_reservation_companions_reservation_id"),
        "reservation_companions",
        ["reservation_id"],
        unique=False,
    )
    op.create_table(
        "reservation_details",
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("amount_paid", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amount_remaining", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("base_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("promotion_discount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("final_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("customer_document_number", sa.String(length=32), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_email", sa.String(length=254), nullable=True),
        sa.Column("room_name", sa.String(length=150), nullable=True),
        sa.Column("stay_days", sa.Integer(), nullable=False),
        sa.Column("unit_rate", sa.Numeric(precision=12, scale=2), nullable=False),
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
            "amount_paid >= 0 AND amount_remaining >= 0 AND round(amount_paid + amount_remaining - final_total, 2) = 0",
            name=op.f("ck_reservation_details_valid_balance"),
        ),
        sa.CheckConstraint(
            "stay_days >= 1", name=op.f("ck_reservation_details_positive_stay_days")
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
            name=op.f("fk_reservation_details_reservation_id_reservations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("reservation_id", name=op.f("pk_reservation_details")),
    )

    methods = sa.table(
        "payment_methods",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        methods,
        [
            {"id": UUID(f"0c1755ec-885f-48ec-a6e0-3387af91f51{index}"), "code": code, "name": name}
            for index, (code, name) in enumerate(
                (
                    ("TARJETA", "Tarjeta"),
                    ("TRANSFERENCIA", "Transferencia"),
                    ("EFECTIVO", "Efectivo"),
                    ("CULQI", "Culqi"),
                ),
                1,
            )
        ],
    )


def downgrade() -> None:
    op.drop_table("reservation_details")
    op.drop_table("reservation_companions")
    op.drop_table("reservations")
    op.drop_table("payment_methods")

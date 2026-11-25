"""Register customers from confirmed reservations."""

import sqlalchemy as sa
from alembic import op

revision = "5e423db988a6"
down_revision = "bb66aee52896"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("identity_key", sa.String(320), nullable=False, unique=True),
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
        sa.Column("document_number", sa.String(32)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255)),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column(
            "country_code",
            sa.String(2),
            sa.ForeignKey("ubigeo_countries.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reservation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("city", sa.String(150), nullable=False),
        sa.Column(
            "district_code",
            sa.String(6),
            sa.ForeignKey("ubigeo_districts.code", ondelete="RESTRICT"),
        ),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "reservations",
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="RESTRICT")),
    )
    op.create_index("ix_reservations_customer_id", "reservations", ["customer_id"])
    op.execute(
        """
        CREATE FUNCTION register_confirmed_customer() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            customer_key text;
            guest_name text;
            first_names text;
            last_names text;
            guest_district text;
            comma_pos integer;
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.customer_id IS NOT NULL THEN
                NEW.customer_id := OLD.customer_id;
                RETURN NEW;
            END IF;

            IF NEW.document_type <> 'SIN DOCUMENTO'
                AND nullif(btrim(NEW.document_number), '') IS NOT NULL THEN
                customer_key := NEW.document_type || ':' || upper(btrim(NEW.document_number));
            ELSE
                customer_key := 'EMAIL:' || lower(btrim(NEW.email));
            END IF;

            guest_name := btrim(regexp_replace(NEW.full_name, '[[:space:]]+', ' ', 'g'));
            comma_pos := strpos(guest_name, ',');
            IF comma_pos > 0 AND btrim(substr(guest_name, comma_pos + 1)) <> '' THEN
                last_names := nullif(btrim(left(guest_name, comma_pos - 1)), '');
                first_names := btrim(substr(guest_name, comma_pos + 1));
            ELSIF strpos(guest_name, ' ') > 0 THEN
                last_names := regexp_replace(guest_name, '^.* ', '');
                first_names := left(guest_name, length(guest_name) - length(last_names) - 1);
            ELSE
                first_names := guest_name;
            END IF;

            IF NEW.country_code = 'PE' THEN
                SELECT min(district.code) INTO guest_district
                FROM ubigeo_districts district
                JOIN ubigeo_provinces province ON province.code = district.province_code
                JOIN ubigeo_departments department ON department.code = province.department_code
                WHERE district.code = btrim(NEW.district)
                   OR (
                    translate(upper(district.name), 'ÁÉÍÓÚÜ', 'AEIOUU')
                        = translate(upper(btrim(NEW.district)), 'ÁÉÍÓÚÜ', 'AEIOUU')
                    AND translate(upper(province.name), 'ÁÉÍÓÚÜ', 'AEIOUU')
                        = translate(upper(btrim(NEW.city)), 'ÁÉÍÓÚÜ', 'AEIOUU')
                    AND translate(upper(department.name), 'ÁÉÍÓÚÜ', 'AEIOUU')
                        = translate(upper(btrim(NEW.region)), 'ÁÉÍÓÚÜ', 'AEIOUU')
                   )
                HAVING count(*) = 1;
            END IF;

            INSERT INTO customers (
                id, identity_key, document_type, document_number, name, last_name, phone,
                email, country_code, reservation_count, city, district_code, address
            ) VALUES (
                gen_random_uuid(), customer_key, NEW.document_type, NEW.document_number,
                first_names, last_names, NEW.phone, NEW.email, NEW.country_code, 1,
                NEW.city, guest_district, NEW.address
            )
            ON CONFLICT (identity_key) DO UPDATE SET
                document_type = excluded.document_type,
                document_number = excluded.document_number,
                name = excluded.name,
                last_name = excluded.last_name,
                phone = excluded.phone,
                email = excluded.email,
                country_code = excluded.country_code,
                reservation_count = customers.reservation_count + 1,
                city = excluded.city,
                district_code = excluded.district_code,
                address = excluded.address,
                updated_at = now()
            RETURNING id INTO NEW.customer_id;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER register_confirmed_customer
        BEFORE INSERT OR UPDATE OF status ON reservations
        FOR EACH ROW WHEN (NEW.status = 'CONFIRMADO')
        EXECUTE FUNCTION register_confirmed_customer()
        """
    )
    op.execute(
        """
        DO $$
        DECLARE confirmed_id uuid;
        BEGIN
            FOR confirmed_id IN
                SELECT id FROM reservations WHERE status = 'CONFIRMADO' ORDER BY created_at, id
            LOOP
                UPDATE reservations SET status = 'CONFIRMADO' WHERE id = confirmed_id;
            END LOOP;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER register_confirmed_customer ON reservations")
    op.execute("DROP FUNCTION register_confirmed_customer()")
    op.drop_index("ix_reservations_customer_id", table_name="reservations")
    op.drop_column("reservations", "customer_id")
    op.drop_table("customers")

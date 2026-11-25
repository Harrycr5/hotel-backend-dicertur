from io import StringIO

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_chain_and_postgresql_sql():
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "2b25d38d348a"
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        "2b25d38d348a",
        "9a7dd23b61c0",
        "70db419e12c3",
        "e274fc8395b0",
        "8a4df09c721e",
        "5e423db988a6",
        "bb66aee52896",
        "7bb89ee312ac",
        "f54f3f44c129",
        "49a8c23b7d10",
        "ab4509f27406",
        "11577c2bf40d",
        "34aa51c993b7",
        "7f458278ac9e",
        "1d76eb56a3fc",
        "c4f9db76307e",
        "af21bde63c48",
        "6c2cc6e7d991",
        "e3b426c8ad51",
        "d72a48f0e196",
        "b0d80c690963",
        "911b7d3f0603",
    ]
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for table in ("users", "profiles", "permissions", "profile_permissions", "auth_sessions"):
        assert f"CREATE TABLE {table}" in sql
    assert sql.index("CREATE TABLE profiles") < sql.index("INSERT INTO profiles")
    assert "refresh_token_hash VARCHAR(64)" in sql
    assert "CREATE TABLE persons" in sql
    assert "CREATE TABLE companies" in sql
    assert "CREATE TABLE company_branches" in sql
    assert "CREATE TABLE room_types" in sql
    assert "CREATE TABLE room_rates" in sql
    for table in (
        "payment_methods",
        "reservations",
        "reservation_companions",
        "reservation_details",
    ):
        assert f"CREATE TABLE {table} (" in sql
    assert sql.count("INSERT INTO payment_methods") == 5
    assert "CREATE TRIGGER notify_reservation_expiration" in sql
    assert "CREATE TABLE customers (" in sql
    assert "CREATE TABLE culqi_charges (" in sql
    assert "CREATE TABLE reservation_payments (" in sql
    assert "'reservations.record_payment'" in sql
    assert "'tills.transfer'" in sql
    assert "'reports.export'" in sql
    assert "CREATE UNIQUE INDEX uq_culqi_charges_processing_reservation" in sql
    for table in ("tills", "till_concepts", "till_shifts", "till_movements", "till_operations"):
        assert f"CREATE TABLE {table} (" in sql
    assert "CREATE UNIQUE INDEX uq_till_shifts_open_till" in sql
    assert sql.count("INSERT INTO till_concepts") == 5
    assert "'YAPE'" in sql
    assert "CREATE TRIGGER register_confirmed_customer" in sql
    assert "ACCION REQUERIDA" not in sql
    for table in ("room_floors", "rooms", "room_images", "room_rate_links"):
        assert f"CREATE TABLE {table} (" in sql
    assert sql.count("INSERT INTO room_floors") == 5
    category_inserts = [
        line for line in sql.splitlines() if line.startswith("INSERT INTO room_categories")
    ]
    assert len(category_inserts) == 3
    for name in ("Estándar", "Superior", "Premium"):
        assert any(f"'{name}'" in statement for statement in category_inserts)
    assert "FOREIGN KEY(category_id) REFERENCES room_categories (id)" in sql
    assert "CHECK (status IN ('DISPONIBLE', 'OCUPADO', 'MANTENIMIENTO', 'RESERVADO'))" in sql
    room_type_inserts = [
        line for line in sql.splitlines() if line.startswith("INSERT INTO room_types")
    ]
    expected_room_types = (
        "Individuales o simples",
        "Dobles y matrimoniales",
        "Suites (incluye sala)",
        "Triples",
        "Bungalós (casas pequeñas)",
    )
    assert len(room_type_inserts) == len(expected_room_types)
    for statement, name in zip(room_type_inserts, expected_room_types, strict=True):
        assert f"'{name}'" in statement
    assert "UNIQUE (ruc)" in sql
    assert sql.count("FOREIGN KEY(district_code) REFERENCES ubigeo_districts (code)") == 3
    assert (
        "ALTER TABLE persons ADD COLUMN is_permanent_employee BOOLEAN DEFAULT false NOT NULL" in sql
    )
    for field in ("document_type", "area", "category"):
        assert f"CHECK ({field} IN (" in sql
    assert "CONSTRAINT ck_persons_gender CHECK (gender IN ('MASCULINO', 'FEMENINO'))" in sql
    for table in (
        "ubigeo_countries",
        "ubigeo_departments",
        "ubigeo_provinces",
        "ubigeo_districts",
    ):
        assert sql.index(f"CREATE TABLE {table}") < sql.index(f"INSERT INTO {table}")
    assert "VALUES ('AD', 'Andorra')" in sql
    assert "VALUES ('PE', 'Perú')" in sql

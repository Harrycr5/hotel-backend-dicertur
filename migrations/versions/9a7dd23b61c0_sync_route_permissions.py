"""Register the permissions declared by the operational routers."""

from alembic import op

from app.core.permissions import permission_catalog_insert

revision = "9a7dd23b61c0"
down_revision = "70db419e12c3"
branch_labels = None
depends_on = None

ROUTE_PERMISSIONS = (
    ("companies.create", "Crear ? empresas"),
    ("companies.delete", "Eliminar ? empresas"),
    ("companies.read", "Consultar ? empresas"),
    ("companies.update", "Actualizar ? empresas"),
    ("company_branches.create", "Crear ? sucursales"),
    ("company_branches.delete", "Eliminar ? sucursales"),
    ("company_branches.read", "Consultar ? sucursales"),
    ("company_branches.update", "Actualizar ? sucursales"),
    ("culqi.charge", "Cobrar ? Culqi"),
    ("culqi.read", "Consultar ? Culqi"),
    ("culqi.reconcile", "Conciliar ? Culqi"),
    ("customers.read", "Consultar ? clientes"),
    ("payment_methods.read", "Consultar ? m?todos de pago"),
    ("permissions.read", "Consultar ? permisos"),
    ("persons.create", "Crear ? personas"),
    ("persons.delete", "Eliminar ? personas"),
    ("persons.read", "Consultar ? personas"),
    ("persons.update", "Actualizar ? personas"),
    ("profiles.create", "Crear ? perfiles"),
    ("profiles.read", "Consultar ? perfiles"),
    ("profiles.update", "Actualizar ? perfiles"),
    ("reservations.cancel", "Cancelar ? reservas"),
    ("reservations.create", "Crear ? reservas"),
    ("reservations.read", "Consultar ? reservas"),
    ("reservations.read_payments", "Consultar pagos ? reservas"),
    ("reservations.record_payment", "Registrar pagos ? reservas"),
    ("room_categories.read", "Consultar ? categor?as de habitaci?n"),
    ("room_floors.create", "Crear ? pisos"),
    ("room_floors.delete", "Eliminar ? pisos"),
    ("room_floors.read", "Consultar ? pisos"),
    ("room_floors.update", "Actualizar ? pisos"),
    ("room_images.create", "Crear ? fotos de habitaci?n"),
    ("room_images.delete", "Eliminar ? fotos de habitaci?n"),
    ("room_rates.create", "Crear ? tarifas"),
    ("room_rates.delete", "Eliminar ? tarifas"),
    ("room_rates.read", "Consultar ? tarifas"),
    ("room_rates.update", "Actualizar ? tarifas"),
    ("room_types.create", "Crear ? tipos de habitaci?n"),
    ("room_types.delete", "Eliminar ? tipos de habitaci?n"),
    ("room_types.read", "Consultar ? tipos de habitaci?n"),
    ("room_types.update", "Actualizar ? tipos de habitaci?n"),
    ("rooms.create", "Crear ? habitaciones"),
    ("rooms.delete", "Eliminar ? habitaciones"),
    ("rooms.read", "Consultar ? habitaciones"),
    ("rooms.update", "Actualizar ? habitaciones"),
    ("till_concepts.create", "Crear ? conceptos de caja"),
    ("till_concepts.read", "Consultar ? conceptos de caja"),
    ("till_movements.create", "Crear ? movimientos de caja"),
    ("till_movements.read", "Consultar ? movimientos de caja"),
    ("till_movements.void", "Anular ? movimientos de caja"),
    ("till_shifts.read", "Consultar ? turnos de caja"),
    ("tills.close", "Cerrar turno ? cajas"),
    ("tills.create", "Crear ? cajas"),
    ("tills.open", "Abrir turno ? cajas"),
    ("tills.read", "Consultar ? cajas"),
    ("tills.transfer", "Transferir efectivo ? cajas"),
    ("users.read", "Consultar ? usuarios"),
    ("users.update", "Actualizar ? usuarios"),
)


def upgrade() -> None:
    op.execute(
        permission_catalog_insert(
            [
                {"code": code, "name": name, "description": f"Permite: {name}."}
                for code, name in ROUTE_PERMISSIONS
            ]
        )
    )


def downgrade() -> None:
    # Preserve permission IDs and any profile assignments made after the upgrade.
    pass

import logging
import re
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

logger = logging.getLogger("alembic.permissions")

VALID_PERMISSION = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
DECLARED_PERMISSIONS: set[str] = set()

ACTION_LABELS = {
    "read": "Consultar",
    "create": "Crear",
    "update": "Actualizar",
    "delete": "Eliminar",
    "read_payments": "Consultar pagos",
    "record_payment": "Registrar pagos",
    "cancel": "Cancelar",
    "open": "Abrir turno",
    "close": "Cerrar turno",
    "transfer": "Transferir efectivo",
    "void": "Anular",
    "charge": "Cobrar",
    "reconcile": "Conciliar",
    "export": "Exportar",
    "guests_export": "Exportar registro de huéspedes",
}

RESOURCE_LABELS = {
    "companies": "empresas",
    "company_branches": "sucursales",
    "culqi": "Culqi",
    "customers": "clientes",
    "payment_methods": "m?todos de pago",
    "permissions": "permisos",
    "persons": "personas",
    "profiles": "perfiles",
    "reservations": "reservas",
    "reports": "reportes",
    "room_categories": "categor?as de habitaci?n",
    "room_floors": "pisos",
    "room_images": "fotos de habitaci?n",
    "room_rates": "tarifas",
    "room_types": "tipos de habitaci?n",
    "rooms": "habitaciones",
    "till_concepts": "conceptos de caja",
    "till_movements": "movimientos de caja",
    "till_shifts": "turnos de caja",
    "tills": "cajas",
    "users": "usuarios",
}


def declare_route_permission(code: str) -> None:
    if len(code) > 100 or not VALID_PERMISSION.fullmatch(code):
        raise ValueError(f"C?digo de permiso inv?lido: {code!r}")
    DECLARED_PERMISSIONS.add(code)


def get_permission_definitions() -> list[dict[str, str]]:
    # Import once so every protected route can declare its permission.
    from app.api.router import api_router  # noqa: F401

    definitions = []
    for code in sorted(DECLARED_PERMISSIONS):
        resource, action = code.split(".")
        label = ACTION_LABELS.get(action, action.replace("_", " ").capitalize())
        name = RESOURCE_LABELS.get(resource, resource.replace("_", " "))
        definitions.append(
            {
                "code": code,
                "name": f"{label} ? {name}"[:100],
                "description": f"Permite {label.lower()} en {name}.",
            }
        )
    return definitions


def permission_catalog_insert(definitions: list[dict[str, str]]):
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("code", sa.String(100)),
        sa.column("name", sa.String(100)),
        sa.column("description", sa.String(255)),
    )
    rows = [{"id": uuid4(), **definition} for definition in definitions]
    return insert(permissions).values(rows).on_conflict_do_nothing(index_elements=["code"])


def sync_route_permissions(connection: Connection) -> None:
    definitions = get_permission_definitions()
    inserted_count = 0
    for start in range(0, len(definitions), 500):
        statement = permission_catalog_insert(definitions[start : start + 500])
        inserted_count += connection.execute(statement).rowcount
    logger.info("Cat?logo de permisos sincronizado: %s nuevos.", inserted_count)

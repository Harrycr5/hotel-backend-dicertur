"""Register the DIRCETUR report export permission."""

from alembic import op

from app.core.permissions import permission_catalog_insert

revision = "2b25d38d348a"
down_revision = "9a7dd23b61c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        permission_catalog_insert(
            [
                {
                    "code": "reports.export",
                    "name": "Exportar · reportes",
                    "description": "Permite exportar reportes.",
                }
            ]
        )
    )


def downgrade() -> None:
    # Preserve the catalog entry and its profile assignments.
    pass

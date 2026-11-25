"""Notify the reservation worker when a deadline needs scheduling."""

from alembic import op

revision = "7bb89ee312ac"
down_revision = "f54f3f44c129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION notify_reservation_expiration() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify('reservation_expiration', '');
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER notify_reservation_expiration
        AFTER INSERT OR UPDATE OF created_at, status ON reservations
        FOR EACH ROW WHEN (NEW.status = 'RESERVADO')
        EXECUTE FUNCTION notify_reservation_expiration()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER notify_reservation_expiration ON reservations")
    op.execute("DROP FUNCTION notify_reservation_expiration()")

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from asyncpg import InterfaceError, PostgresError
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, engine
from app.modules.culqi.models import PROCESSING, CulqiCharge

from .choices import ReservationStatus
from .models import Reservation, ReservationDetail

logger = logging.getLogger(__name__)
RESERVATION_HOLD = timedelta(hours=24)
EXPIRATION_CHANNEL = "reservation_expiration"


def paid_status(amount_paid: Decimal, final_total: Decimal) -> ReservationStatus:
    if amount_paid == 0:
        return ReservationStatus.BOOKED
    if amount_paid == final_total:
        return ReservationStatus.CONFIRMED
    return ReservationStatus.PARTIALLY_PAID


def hold_has_expired(created_at: datetime, now: datetime) -> bool:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at <= now - RESERVATION_HOLD


def processing_charge_exists():
    return (
        select(CulqiCharge.id)
        .where(CulqiCharge.reservation_id == Reservation.id, CulqiCharge.status == PROCESSING)
        .exists()
    )


async def has_processing_charge(session: AsyncSession, reservation_id: UUID) -> bool:
    return bool(
        await session.scalar(
            select(
                select(CulqiCharge.id)
                .where(
                    CulqiCharge.reservation_id == reservation_id, CulqiCharge.status == PROCESSING
                )
                .exists()
            )
        )
    )


def unpaid_reservation_conditions():
    paid_detail_exists = (
        select(ReservationDetail.reservation_id)
        .where(
            ReservationDetail.reservation_id == Reservation.id, ReservationDetail.amount_paid > 0
        )
        .exists()
    )
    return (
        Reservation.status == ReservationStatus.BOOKED,
        or_(Reservation.payment_amount.is_(None), Reservation.payment_amount == 0),
        ~paid_detail_exists,
        ~processing_charge_exists(),
    )


async def expire_unpaid_reservations(session: AsyncSession, now: datetime) -> None:
    cutoff = Reservation.created_at <= now - RESERVATION_HOLD
    locked_ids = (
        await session.scalars(
            select(Reservation.id)
            .where(*unpaid_reservation_conditions(), cutoff)
            .order_by(Reservation.id)
            .with_for_update()
        )
    ).all()
    if not locked_ids:
        return
    # Read pending charges again after taking the same reservation locks used by payments.
    await session.execute(
        update(Reservation)
        .where(
            Reservation.id.in_(locked_ids),
            *unpaid_reservation_conditions(),
            cutoff,
        )
        .values(status=ReservationStatus.EXPIRED)
    )


async def next_expiration(session: AsyncSession) -> datetime | None:
    created_at = await session.scalar(
        select(func.min(Reservation.created_at)).where(*unpaid_reservation_conditions())
    )
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + RESERVATION_HOLD


async def listen_for_expirations() -> None:
    changed = asyncio.Event()

    def wake_up(*_):
        changed.set()

    async with engine.connect() as connection:
        raw = (await connection.get_raw_connection()).driver_connection
        raw.add_termination_listener(wake_up)
        try:
            await raw.add_listener(EXPIRATION_CHANNEL, wake_up)
            while not raw.is_closed():
                # A notification during the query must remain set until the next iteration.
                changed.clear()
                async with AsyncSessionLocal() as session, session.begin():
                    await expire_unpaid_reservations(session, datetime.now(timezone.utc))
                    deadline = await next_expiration(session)
                if deadline is None:
                    await changed.wait()
                else:
                    delay = (deadline - datetime.now(timezone.utc)).total_seconds()
                    if delay > 0:
                        try:
                            await asyncio.wait_for(changed.wait(), timeout=delay)
                        except TimeoutError:
                            pass
        finally:
            if not raw.is_closed():
                raw.remove_termination_listener(wake_up)
                await raw.remove_listener(EXPIRATION_CHANNEL, wake_up)


async def run_reservation_expiration() -> None:
    while True:
        try:
            await listen_for_expirations()
        except (SQLAlchemyError, PostgresError, InterfaceError, OSError):
            logger.exception("Se perdió la conexión del worker de caducidad de reservas.")
        await asyncio.sleep(5)

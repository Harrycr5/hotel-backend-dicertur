import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from asyncpg import InterfaceError, PostgresError
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.dependencies import DbSession
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.db.session import AsyncSessionLocal, engine
from app.modules.culqi.models import PROCESSING, CulqiCharge
from app.modules.payment_methods.models import PaymentMethod
from app.modules.rooms.models import Rate, Room
from app.modules.ubigee.models import Country

from .choices import ReservationStatus
from .models import (
    Companion,
    Reservation,
    ReservationDetail,
    ReservationDiscountCode,
    ReservationPayment,
)
from .schemas import PERU_TIME, ReservationCreate

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


reservation_query = select(Reservation).options(
    joinedload(Reservation.room).joinedload(Room.room_type),
    joinedload(Reservation.rate),
    selectinload(Reservation.companions),
    selectinload(Reservation.detail),
)


async def find_reservation(session: DbSession, reservation_id: UUID, *, lock: bool = False):
    query = reservation_query.where(Reservation.id == reservation_id)
    if lock:
        query = query.with_for_update(of=Reservation)
    reservation = await session.scalar(query)
    if reservation is None:
        raise NotFoundError("Reserva no encontrada.")
    return reservation


async def validate_method(session: DbSession, method_id: UUID) -> None:
    method = await session.get(PaymentMethod, method_id)
    if method is None:
        raise NotFoundError("Método de pago no encontrado.")
    if not method.is_active:
        raise ConflictError("El método de pago está inactivo.")


def initial_status(data: ReservationCreate, now: datetime) -> ReservationStatus:
    detail = data.detail
    paid = detail.amount_paid if detail else Decimal("0")
    if data.payment_amount is not None and data.payment_amount > paid:
        raise AppError("El importe del pago requiere un detalle con el monto acumulado pagado.")
    if data.status == ReservationStatus.CANCELED:
        return data.status
    if data.status == ReservationStatus.WITHOUT_PAYMENT:
        if paid > 0:
            raise AppError("Una reserva sin pagos no puede registrar un monto pagado.")
        return data.status

    computed = paid_status(paid, detail.final_total) if detail else ReservationStatus.BOOKED
    if computed == ReservationStatus.BOOKED and hold_has_expired(data.created_at or now, now):
        computed = ReservationStatus.EXPIRED
    if data.status not in (ReservationStatus.BOOKED, computed):
        raise AppError("El estado indicado no corresponde al pago o a la antigüedad de la reserva.")
    return computed


async def apply_reservation_discount(
    session: AsyncSession, reservation: Reservation, room_type_id: UUID, code: str, now: datetime
) -> None:
    code = code.strip().upper()
    detail = reservation.detail
    if reservation.discount_code == code and detail is not None and detail.promotion_discount > 0:
        return
    if reservation.discount_code not in (None, code):
        raise ConflictError("La reserva ya tiene otro código de descuento.")
    promotion = await session.get(ReservationDiscountCode, code)
    if promotion is None:
        raise NotFoundError("Código de descuento no encontrado.")
    today = now.astimezone(PERU_TIME).date()
    if (
        not promotion.is_active
        or promotion.start_date is None
        or promotion.end_date is None
        or promotion.discount_percentage is None
        or not promotion.start_date <= today <= promotion.end_date
    ):
        raise ConflictError("El código de descuento no está vigente.")
    if promotion.room_type_id != room_type_id:
        raise ConflictError("El código no aplica al tipo de habitación de la reserva.")
    if (
        not reservation.is_active
        or reservation.status != ReservationStatus.BOOKED
        or hold_has_expired(reservation.created_at, now)
    ):
        raise ConflictError("La reserva no admite descuentos en su estado actual.")
    if detail is None or detail.amount_paid > 0 or detail.promotion_discount > 0:
        raise ConflictError("Se requiere un detalle sin abonos ni descuentos previos.")
    discount = (detail.final_total * promotion.discount_percentage / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if discount <= 0:
        raise ConflictError("El descuento es menor a un céntimo para el importe de la reserva.")
    detail.promotion_discount = discount
    detail.final_total -= discount
    detail.amount_remaining = detail.final_total
    reservation.discount_code = code
    if detail.final_total == 0:
        reservation.status = ReservationStatus.WITHOUT_PAYMENT


async def stage_reservation(data: ReservationCreate, session: AsyncSession) -> Reservation:
    room = await session.get(Room, data.room_id)
    if room is None:
        raise NotFoundError("Habitación no encontrada.")
    if await session.get(Rate, data.rate_id) is None:
        raise NotFoundError("Tarifa no encontrada.")
    if await session.get(Country, data.country_code) is None:
        raise NotFoundError("País no encontrado.")
    if data.payment_method_id is not None:
        await validate_method(session, data.payment_method_id)
    now = datetime.now(timezone.utc)
    values = data.model_dump(
        exclude={"status", "companions", "detail", "created_at", "discount_code"}
    )
    reservation = Reservation(
        **values,
        created_at=data.created_at or now,
        status=initial_status(data, now),
        companions=[Companion(**person.model_dump()) for person in data.companions],
        detail=ReservationDetail(**data.detail.model_dump(exclude_none=True))
        if data.detail
        else None,
    )
    if data.discount_code is not None:
        await apply_reservation_discount(
            session, reservation, room.room_type_id, data.discount_code, now
        )
    session.add(reservation)
    if data.payment_method_id is not None and data.payment_amount:
        await session.flush()
        session.add(
            ReservationPayment(
                reservation_id=reservation.id,
                payment_method_id=data.payment_method_id,
                amount=data.payment_amount,
            )
        )
    await session.flush()
    return reservation

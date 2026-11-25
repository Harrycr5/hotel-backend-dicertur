from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select, true
from sqlalchemy.orm import joinedload, selectinload

from app.api.dependencies import DbSession
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions
from app.modules.payment_methods.models import PaymentMethod
from app.modules.rooms.models import Rate, Room
from app.modules.ubigee.models import Country

from .choices import ReservationStatus
from .models import Companion, Reservation, ReservationDetail, ReservationPayment
from .schemas import (
    PaymentUpdate,
    ReservationCreate,
    ReservationPaymentMethodRead,
    ReservationPaymentsRead,
    ReservationRead,
    ReservationStatusRead,
)
from .service import (
    expire_unpaid_reservations,
    has_processing_charge,
    hold_has_expired,
    paid_status,
)

router = APIRouter(prefix="/reservations", tags=["Reservations"])
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


@router.get(
    "/statuses",
    summary="Listar estados de reserva",
    response_model=ApiResponse[list[ReservationStatusRead]],
    dependencies=[Depends(require_permissions("reservations.read"))],
)
async def list_statuses():
    return ApiResponse[list[ReservationStatusRead]](
        data=[
            ReservationStatusRead(value=option, label=option.label) for option in ReservationStatus
        ]
    )


@router.get(
    "",
    summary="Listar reservas",
    response_model=ApiResponse[Page[ReservationRead]],
    dependencies=[Depends(require_permissions("reservations.read"))],
)
async def list_reservations(session: DbSession, pagination: Pagination):
    await expire_unpaid_reservations(session, datetime.now(timezone.utc))
    await session.commit()
    total = await session.scalar(select(func.count()).select_from(Reservation))
    reservations = await session.scalars(
        reservation_query.order_by(Reservation.created_at.desc(), Reservation.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[ReservationRead]](
        data=Page[ReservationRead].build(
            [ReservationRead.model_validate(reservation) for reservation in reservations],
            total or 0,
            pagination,
        )
    )


@router.post(
    "",
    summary="Crear reserva",
    response_model=ApiResponse[ReservationRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("reservations.create"))],
)
async def create_reservation(data: ReservationCreate, session: DbSession):
    if await session.get(Room, data.room_id) is None:
        raise NotFoundError("Habitación no encontrada.")
    if await session.get(Rate, data.rate_id) is None:
        raise NotFoundError("Tarifa no encontrada.")
    if await session.get(Country, data.country_code) is None:
        raise NotFoundError("País no encontrado.")
    if data.payment_method_id is not None:
        await validate_method(session, data.payment_method_id)

    now = datetime.now(timezone.utc)
    values = data.model_dump(exclude={"status", "companions", "detail", "created_at"})
    reservation = Reservation(
        **values,
        created_at=data.created_at or now,
        status=initial_status(data, now),
        companions=[Companion(**person.model_dump()) for person in data.companions],
        detail=ReservationDetail(**data.detail.model_dump(exclude_none=True))
        if data.detail
        else None,
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
    await session.commit()
    reservation = await find_reservation(session, reservation.id)
    return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))


@router.get(
    "/{reservation_id}",
    summary="Consultar reserva",
    response_model=ApiResponse[ReservationRead],
    dependencies=[Depends(require_permissions("reservations.read"))],
)
async def get_reservation(reservation_id: UUID, session: DbSession):
    await expire_unpaid_reservations(session, datetime.now(timezone.utc))
    await session.commit()
    reservation = await find_reservation(session, reservation_id)
    return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))


@router.get(
    "/{reservation_id}/payments",
    summary="Consultar métodos de pago usados en la reserva",
    response_model=ApiResponse[ReservationPaymentsRead],
    dependencies=[Depends(require_permissions("reservations.read_payments"))],
)
async def get_reservation_payments(reservation_id: UUID, session: DbSession):
    totals = (
        select(
            PaymentMethod.id,
            PaymentMethod.code,
            PaymentMethod.name,
            func.count(ReservationPayment.id).label("payment_count"),
            func.sum(ReservationPayment.amount).label("amount_paid"),
        )
        .select_from(ReservationPayment)
        .join(PaymentMethod, PaymentMethod.id == ReservationPayment.payment_method_id)
        .where(ReservationPayment.reservation_id == reservation_id)
        .group_by(PaymentMethod.id, PaymentMethod.code, PaymentMethod.name)
        .subquery()
    )
    rows = await session.execute(
        select(ReservationDetail.amount_paid.label("total_paid"), *totals.c)
        .select_from(Reservation)
        .outerjoin(ReservationDetail, ReservationDetail.reservation_id == Reservation.id)
        .outerjoin(totals, true())
        .where(Reservation.id == reservation_id)
        .order_by(totals.c.code)
    )
    payments = rows.all()
    if not payments:
        raise NotFoundError("Reserva no encontrada.")
    methods = [
        ReservationPaymentMethodRead(
            id=row.id,
            code=row.code,
            name=row.name,
            payment_count=row.payment_count,
            amount_paid=row.amount_paid,
        )
        for row in payments
        if row.id is not None
    ]
    total_paid = payments[0].total_paid
    zero = Decimal("0.00")
    return ApiResponse[ReservationPaymentsRead](
        data=ReservationPaymentsRead(
            reservation_id=reservation_id,
            payment_method_count=len(methods),
            methods=methods,
            unattributed_amount=max(
                zero, (total_paid or zero) - sum(m.amount_paid for m in methods)
            ),
        )
    )


@router.patch(
    "/{reservation_id}/payment",
    summary="Registrar pago de una reserva",
    response_model=ApiResponse[ReservationRead],
    dependencies=[Depends(require_permissions("reservations.record_payment"))],
)
async def update_payment(reservation_id: UUID, data: PaymentUpdate, session: DbSession):
    reservation = await find_reservation(session, reservation_id, lock=True)
    if await has_processing_charge(session, reservation_id):
        raise ConflictError("Hay un cargo Culqi pendiente de conciliación.")
    now = datetime.now(timezone.utc)
    if reservation.status == ReservationStatus.BOOKED and hold_has_expired(
        reservation.created_at, now
    ):
        reservation.status = ReservationStatus.EXPIRED
        await session.commit()
    if reservation.status in (
        ReservationStatus.CANCELED,
        ReservationStatus.EXPIRED,
        ReservationStatus.WITHOUT_PAYMENT,
    ):
        raise ConflictError("El estado de la reserva no permite registrar un pago.")
    detail = reservation.detail
    if detail is None:
        raise ConflictError("La reserva necesita un detalle con el total antes de registrar pagos.")
    if not detail.amount_paid <= data.amount_paid <= detail.final_total:
        raise AppError("El monto acumulado debe estar entre lo ya pagado y el total final.")
    if data.amount_paid == detail.amount_paid:
        return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))
    if data.method_id is not None:
        await validate_method(session, data.method_id)
        reservation.payment_method_id = data.method_id
    reservation.paid_at = data.paid_at or now
    reservation.payment_amount = data.amount_paid - detail.amount_paid
    if data.method_id is not None:
        session.add(
            ReservationPayment(
                reservation_id=reservation.id,
                payment_method_id=data.method_id,
                amount=reservation.payment_amount,
            )
        )
    reservation.transaction_number = data.transaction_number
    detail.amount_paid = data.amount_paid
    detail.amount_remaining = detail.final_total - data.amount_paid
    reservation.status = paid_status(data.amount_paid, detail.final_total)
    await session.commit()
    reservation = await find_reservation(session, reservation_id)
    return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))


@router.patch(
    "/{reservation_id}/cancel",
    summary="Cancelar reserva",
    response_model=ApiResponse[ReservationRead],
    dependencies=[Depends(require_permissions("reservations.cancel"))],
)
async def cancel_reservation(reservation_id: UUID, session: DbSession):
    reservation = await find_reservation(session, reservation_id, lock=True)
    if await has_processing_charge(session, reservation_id):
        raise ConflictError("Hay un cargo Culqi pendiente de conciliación.")
    if reservation.status == ReservationStatus.EXPIRED:
        raise ConflictError("La reserva ya caducó.")
    if reservation.status == ReservationStatus.BOOKED and hold_has_expired(
        reservation.created_at, datetime.now(timezone.utc)
    ):
        reservation.status = ReservationStatus.EXPIRED
        await session.commit()
        raise ConflictError("La reserva ya caducó.")
    reservation.status = ReservationStatus.CANCELED
    await session.commit()
    return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))

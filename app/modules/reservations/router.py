from datetime import datetime, timezone
from decimal import Decimal
from secrets import randbelow
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.api.dependencies import DbSession
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions
from app.modules.payment_methods.models import PaymentMethod
from app.modules.rooms.models import RoomType

from .choices import ReservationStatus
from .models import Reservation, ReservationDetail, ReservationDiscountCode, ReservationPayment
from .quotes_router import router as quotes_router
from .schemas import (
    PERU_TIME,
    PaymentUpdate,
    ReservationCreate,
    ReservationDiscountApply,
    ReservationDiscountCodeCreate,
    ReservationDiscountCodeFilters,
    ReservationDiscountCodeRead,
    ReservationPaymentMethodRead,
    ReservationPaymentsRead,
    ReservationRead,
    ReservationStatusRead,
)
from .service import (
    apply_reservation_discount,
    expire_unpaid_reservations,
    find_reservation,
    has_processing_charge,
    hold_has_expired,
    paid_status,
    reservation_query,
    stage_reservation,
    validate_method,
)

router = APIRouter(prefix="/reservations", tags=["Reservations"])
router.include_router(quotes_router)


@router.get(
    "/discount-codes",
    summary="Listar códigos de descuento vigentes",
    response_model=ApiResponse[Page[ReservationDiscountCodeRead]],
)
async def list_discount_codes(
    session: DbSession, filters: Annotated[ReservationDiscountCodeFilters, Query()]
):
    today = datetime.now(PERU_TIME).date()
    conditions = [
        ReservationDiscountCode.is_active,
        ReservationDiscountCode.start_date <= today,
        ReservationDiscountCode.end_date >= today,
    ]
    if filters.room_type_id is not None:
        conditions.append(ReservationDiscountCode.room_type_id == filters.room_type_id)
    total = await session.scalar(
        select(func.count()).select_from(ReservationDiscountCode).where(*conditions)
    )
    promotions = await session.scalars(
        select(ReservationDiscountCode)
        .where(*conditions)
        .order_by(ReservationDiscountCode.created_at.desc(), ReservationDiscountCode.code)
        .offset(filters.offset)
        .limit(filters.page_size)
    )
    return ApiResponse[Page[ReservationDiscountCodeRead]](
        data=Page[ReservationDiscountCodeRead].build(
            [ReservationDiscountCodeRead.model_validate(promotion) for promotion in promotions],
            total or 0,
            filters,
        )
    )


@router.post(
    "/discount-codes",
    summary="Generar código de descuento para reservas",
    response_model=ApiResponse[ReservationDiscountCodeRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("reservations.discount_codes_create"))],
)
async def create_discount_code(data: ReservationDiscountCodeCreate, session: DbSession):
    if await session.get(RoomType, data.room_type_id) is None:
        raise NotFoundError("Tipo de habitación no encontrado.")
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    for _ in range(8):
        candidate = f"HT{randbelow(100_000_000):08d}"
        promotion = await session.scalar(
            insert(ReservationDiscountCode)
            .values(code=candidate, **data.model_dump())
            .on_conflict_do_nothing(index_elements=[ReservationDiscountCode.code])
            .returning(ReservationDiscountCode)
        )
        if promotion is not None:
            await session.commit()
            return ApiResponse[ReservationDiscountCodeRead](
                data=ReservationDiscountCodeRead.model_validate(promotion)
            )
    raise HTTPException(503, "No se pudo generar un código. Intenta nuevamente.")


@router.patch(
    "/{reservation_id}/discount-code",
    summary="Aplicar código de descuento a una reserva",
    response_model=ApiResponse[ReservationRead],
    dependencies=[Depends(require_permissions("reservations.discount_codes_apply"))],
)
async def apply_discount_code(
    reservation_id: UUID, data: ReservationDiscountApply, session: DbSession
):
    reservation = await find_reservation(session, reservation_id, lock=True)
    if await has_processing_charge(session, reservation_id):
        raise ConflictError("Hay un cargo Culqi pendiente de conciliación.")
    await apply_reservation_discount(
        session, reservation, reservation.room.room_type_id, data.code, datetime.now(timezone.utc)
    )
    await session.commit()
    return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))


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
    reservation = await stage_reservation(data, session)
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

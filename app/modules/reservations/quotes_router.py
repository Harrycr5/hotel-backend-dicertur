from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.api.dependencies import DbSession
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions
from app.modules.rooms.models import Rate, Room, room_rate_links

from .choices import ReservationStatus
from .models import Reservation, ReservationQuote
from .schemas import (
    PERU_TIME,
    DetailCreate,
    ReservationCreate,
    ReservationQuoteConvert,
    ReservationQuoteCreate,
    ReservationQuoteLink,
    ReservationQuoteRead,
    ReservationRead,
)
from .service import find_reservation, stage_reservation

router = APIRouter(prefix="/quotes")
MAX_QUOTED_TOTAL = Decimal("9999999999.99")


async def get_quote_or_404(session: DbSession, quote_id: UUID, *, lock: bool = False):
    quote = await session.get(ReservationQuote, quote_id, with_for_update=lock)
    if quote is None:
        raise NotFoundError("Cotización no encontrada.")
    return quote


def stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@router.post(
    "/{quote_id}/reservation",
    summary="Crear reserva desde una cotización",
    response_model=ApiResponse[ReservationRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("reservations.create", "reservations.quotes_link"))],
)
async def convert_quote(quote_id: UUID, data: ReservationQuoteConvert, session: DbSession):
    quote = await get_quote_or_404(session, quote_id, lock=True)
    if quote.reservation_id is not None:
        reservation = await find_reservation(session, quote.reservation_id)
        return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))
    if stored_utc(quote.valid_until) <= datetime.now(timezone.utc):
        raise ConflictError("La cotización ya venció.")

    check_in, check_out = stored_utc(quote.check_in), stored_utc(quote.check_out)
    nights = (check_out.astimezone(PERU_TIME).date() - check_in.astimezone(PERU_TIME).date()).days
    if nights < 1:
        raise ConflictError("La cotización debe incluir al menos una noche.")
    detail = DetailCreate(
        amount_remaining=quote.quoted_total,
        base_price=quote.quoted_total,
        final_total=quote.quoted_total,
        stay_days=nights,
        unit_rate=(quote.quoted_total / nights).quantize(Decimal("0.01")),
    )
    reservation = await stage_reservation(
        ReservationCreate(
            **data.model_dump(),
            room_id=quote.room_id,
            rate_id=quote.rate_id,
            check_in=check_in,
            check_out=check_out,
            detail=detail,
        ),
        session,
    )
    quote.reservation_id = reservation.id
    await session.commit()
    reservation = await find_reservation(session, reservation.id)
    return ApiResponse[ReservationRead](data=ReservationRead.model_validate(reservation))


@router.get(
    "",
    summary="Listar cotizaciones de reservas",
    response_model=ApiResponse[Page[ReservationQuoteRead]],
    dependencies=[Depends(require_permissions("reservations.quotes_read"))],
)
async def list_quotes(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(ReservationQuote))
    quotes = await session.scalars(
        select(ReservationQuote)
        .order_by(ReservationQuote.created_at.desc(), ReservationQuote.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[ReservationQuoteRead]](
        data=Page[ReservationQuoteRead].build(
            [ReservationQuoteRead.model_validate(quote) for quote in quotes],
            total or 0,
            pagination,
        )
    )


@router.post(
    "",
    summary="Crear cotización de una habitación",
    response_model=ApiResponse[ReservationQuoteRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("reservations.quotes_create"))],
)
async def create_quote(data: ReservationQuoteCreate, session: DbSession):
    if data.valid_until <= datetime.now(timezone.utc):
        raise AppError("La vigencia de la cotización debe terminar en el futuro.")
    if await session.get(Room, data.room_id) is None:
        raise NotFoundError("Habitación no encontrada.")
    rate = await session.scalar(
        select(Rate)
        .join(room_rate_links, room_rate_links.c.rate_id == Rate.id)
        .where(room_rate_links.c.room_id == data.room_id, Rate.id == data.rate_id, Rate.is_active)
    )
    if rate is None:
        raise ConflictError("La tarifa debe estar activa y asignada a la habitación.")
    total = rate.price * data.nights
    if total > MAX_QUOTED_TOTAL:
        raise AppError("El total cotizado supera el importe permitido.")
    quote = ReservationQuote(**data.model_dump(), quoted_total=total)
    session.add(quote)
    await session.commit()
    await session.refresh(quote)
    return ApiResponse[ReservationQuoteRead](data=ReservationQuoteRead.model_validate(quote))


@router.get(
    "/{quote_id}",
    summary="Consultar cotización",
    response_model=ApiResponse[ReservationQuoteRead],
    dependencies=[Depends(require_permissions("reservations.quotes_read"))],
)
async def get_quote(quote_id: UUID, session: DbSession):
    quote = await get_quote_or_404(session, quote_id)
    return ApiResponse[ReservationQuoteRead](data=ReservationQuoteRead.model_validate(quote))


@router.patch(
    "/{quote_id}/reservation",
    summary="Vincular cotización a una reserva",
    response_model=ApiResponse[ReservationQuoteRead],
    dependencies=[Depends(require_permissions("reservations.quotes_link"))],
)
async def link_quote(quote_id: UUID, data: ReservationQuoteLink, session: DbSession):
    quote = await get_quote_or_404(session, quote_id, lock=True)
    if quote.reservation_id == data.reservation_id:
        return ApiResponse[ReservationQuoteRead](data=ReservationQuoteRead.model_validate(quote))
    if quote.reservation_id is not None:
        raise ConflictError("La cotización ya está vinculada a otra reserva.")
    if stored_utc(quote.valid_until) <= datetime.now(timezone.utc):
        raise ConflictError("La cotización ya venció.")
    reservation = await session.get(Reservation, data.reservation_id, with_for_update=True)
    if reservation is None:
        raise NotFoundError("Reserva no encontrada.")
    if reservation.status in (ReservationStatus.CANCELED, ReservationStatus.EXPIRED):
        raise ConflictError("La reserva está cancelada o caducada.")
    if (
        reservation.room_id != quote.room_id
        or reservation.rate_id != quote.rate_id
        or stored_utc(reservation.check_in) != stored_utc(quote.check_in)
        or stored_utc(reservation.check_out) != stored_utc(quote.check_out)
    ):
        raise ConflictError(
            "La reserva debe coincidir con la habitación, la tarifa y las fechas cotizadas."
        )
    quote.reservation_id = reservation.id
    await session.commit()
    return ApiResponse[ReservationQuoteRead](data=ReservationQuoteRead.model_validate(quote))

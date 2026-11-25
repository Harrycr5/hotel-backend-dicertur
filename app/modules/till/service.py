import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.payment_methods.models import PaymentMethod
from app.modules.reservations.models import Reservation

from .models import Direction, Till, TillConcept, TillMovement, TillOperation, TillShift
from .schemas import (
    MovementCreate,
    MovementRead,
    ShiftClose,
    ShiftOpen,
    ShiftRead,
    TransferCreate,
    TransferRead,
    VoidMovement,
    VoidRead,
)

CASH_CODE = "EFECTIVO"
TRANSFER_CONCEPT = "TRANSFERENCIA_ENTRE_CAJAS"


async def run_operation[Result: BaseModel](
    session: AsyncSession,
    key: str,
    user_id: UUID,
    action: str,
    data: BaseModel,
    handler: Callable[[], Awaitable[Result]],
    response_type: type[Result],
) -> Result:
    payload = json.dumps(data.model_dump(mode="json"), sort_keys=True)
    fingerprint = hashlib.sha256(f"{action}:{payload}".encode()).hexdigest()
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    try:
        claimed = await session.scalar(
            insert(TillOperation)
            .values(key=key, user_id=user_id, fingerprint=fingerprint)
            .on_conflict_do_nothing(index_elements=[TillOperation.key])
            .returning(TillOperation.key)
        )
        operation = await session.get(TillOperation, key)
        if claimed is None:
            if operation.user_id != user_id or operation.fingerprint != fingerprint:
                raise ConflictError("La clave de idempotencia ya se usó para otra operación.")
            result = response_type.model_validate(operation.response)
        else:
            result = await handler()
            operation.response = result.model_dump(mode="json")
        await session.commit()
        return result
    except BaseException:
        await session.rollback()
        raise


async def lock_open_shifts(session: AsyncSession, *shift_ids: UUID) -> dict[UUID, TillShift]:
    shifts = (
        await session.scalars(
            select(TillShift)
            .where(TillShift.id.in_(shift_ids))
            .order_by(TillShift.id)
            .with_for_update()
        )
    ).all()
    if len(shifts) != len(set(shift_ids)):
        raise NotFoundError("Turno de caja no encontrado.")
    if any(shift.closed_at is not None for shift in shifts):
        raise ConflictError("El turno de caja ya está cerrado.")
    return {shift.id: shift for shift in shifts}


async def cash_balance(session: AsyncSession, shift: TillShift) -> Decimal:
    signed_amount = case(
        (TillMovement.direction == Direction.INCOME, TillMovement.amount),
        else_=-TillMovement.amount,
    )
    net_cash = await session.scalar(
        select(func.sum(signed_amount))
        .join(PaymentMethod, PaymentMethod.id == TillMovement.payment_method_id)
        .where(
            TillMovement.shift_id == shift.id,
            TillMovement.voided_at.is_(None),
            PaymentMethod.code == CASH_CODE,
        )
    )
    return shift.opening_amount + (net_cash or Decimal("0.00"))


async def open_shift(
    session: AsyncSession, till_id: UUID, user_id: UUID, data: ShiftOpen
) -> ShiftRead:
    till = await session.get(Till, till_id, with_for_update=True)
    if till is None:
        raise NotFoundError("Caja no encontrada.")
    if not till.is_active:
        raise ConflictError("La caja está inactiva.")
    active_shift = await session.scalar(
        select(TillShift.id).where(TillShift.till_id == till_id, TillShift.closed_at.is_(None))
    )
    if active_shift is not None:
        raise ConflictError("La caja ya tiene un turno abierto.")
    shift = TillShift(
        till_id=till_id,
        opened_by_id=user_id,
        opened_at=datetime.now(timezone.utc),
        opening_amount=data.opening_amount,
    )
    session.add(shift)
    await session.flush()
    return ShiftRead.model_validate(shift)


async def close_shift(
    session: AsyncSession, shift_id: UUID, user_id: UUID, data: ShiftClose
) -> ShiftRead:
    shift = (await lock_open_shifts(session, shift_id))[shift_id]
    shift.expected_cash = await cash_balance(session, shift)
    shift.counted_cash = data.counted_cash
    shift.difference = data.counted_cash - shift.expected_cash
    shift.closed_at = datetime.now(timezone.utc)
    shift.closed_by_id = user_id
    await session.flush()
    return ShiftRead.model_validate(shift)


async def record_movement(
    session: AsyncSession, shift_id: UUID, user_id: UUID, data: MovementCreate
) -> MovementRead:
    await lock_open_shifts(session, shift_id)
    concept = await session.get(TillConcept, data.concept_id)
    method = await session.get(PaymentMethod, data.payment_method_id)
    if concept is None or method is None:
        raise NotFoundError("Concepto o método de pago no encontrado.")
    if not concept.is_active or not method.is_active or concept.code == TRANSFER_CONCEPT:
        raise ConflictError("El concepto o método no está disponible para este movimiento.")
    if (
        data.reservation_id is not None
        and await session.get(Reservation, data.reservation_id) is None
    ):
        raise NotFoundError("Reserva no encontrada.")
    movement = TillMovement(shift_id=shift_id, registered_by_id=user_id, **data.model_dump())
    session.add(movement)
    await session.flush()
    return MovementRead.model_validate(movement)


async def transfer_cash(session: AsyncSession, user_id: UUID, data: TransferCreate) -> TransferRead:
    if data.source_shift_id == data.destination_shift_id:
        raise ConflictError("La caja de origen y destino deben ser distintas.")
    shifts = await lock_open_shifts(session, data.source_shift_id, data.destination_shift_id)
    source = shifts[data.source_shift_id]
    destination = shifts[data.destination_shift_id]
    if source.till_id == destination.till_id:
        raise ConflictError("La caja de origen y destino deben ser distintas.")
    if await cash_balance(session, source) < data.amount:
        raise ConflictError("La caja de origen no tiene efectivo suficiente.")
    method_id = await session.scalar(
        select(PaymentMethod.id).where(PaymentMethod.code == CASH_CODE, PaymentMethod.is_active)
    )
    concept_id = await session.scalar(
        select(TillConcept.id).where(TillConcept.code == TRANSFER_CONCEPT, TillConcept.is_active)
    )
    if method_id is None or concept_id is None:
        raise ConflictError(
            "El método Efectivo y el concepto de transferencia deben estar activos."
        )
    transfer_id = uuid4()
    fields = dict(
        transfer_id=transfer_id,
        concept_id=concept_id,
        payment_method_id=method_id,
        registered_by_id=user_id,
        amount=data.amount,
        notes=data.notes,
    )
    expense = TillMovement(shift_id=source.id, direction=Direction.EXPENSE, **fields)
    income = TillMovement(shift_id=destination.id, direction=Direction.INCOME, **fields)
    session.add_all([expense, income])
    await session.flush()
    return TransferRead(
        id=transfer_id,
        expense=MovementRead.model_validate(expense),
        income=MovementRead.model_validate(income),
    )


async def void_movement(
    session: AsyncSession, movement_id: UUID, user_id: UUID, data: VoidMovement
) -> VoidRead:
    movement = await session.get(TillMovement, movement_id)
    if movement is None:
        raise NotFoundError("Movimiento no encontrado.")
    criterion = (
        TillMovement.id == movement_id
        if movement.transfer_id is None
        else TillMovement.transfer_id == movement.transfer_id
    )
    shift_ids = (await session.scalars(select(TillMovement.shift_id).where(criterion))).all()
    await lock_open_shifts(session, *shift_ids)
    entries = (
        await session.scalars(
            select(TillMovement)
            .where(criterion)
            .order_by(TillMovement.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    if any(entry.voided_at is not None for entry in entries):
        raise ConflictError("El movimiento ya fue anulado.")
    now = datetime.now(timezone.utc)
    for entry in entries:
        entry.voided_at = now
        entry.voided_by_id = user_id
        entry.void_reason = data.reason
    await session.flush()
    return VoidRead(movements=[MovementRead.model_validate(entry) for entry in entries])

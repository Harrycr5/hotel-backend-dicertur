from functools import partial
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser, require_permissions

from . import service
from .models import Till, TillConcept, TillMovement, TillShift
from .schemas import (
    ConceptCreate,
    ConceptRead,
    MovementCreate,
    MovementRead,
    ShiftClose,
    ShiftOpen,
    ShiftRead,
    TillCreate,
    TillRead,
    TransferCreate,
    TransferRead,
    VoidMovement,
    VoidRead,
)

router = APIRouter(prefix="/tills", tags=["Till"])
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=100, pattern=r"^[!-~]+$")
]


@router.get(
    "",
    summary="Listar cajas",
    response_model=ApiResponse[list[TillRead]],
    dependencies=[Depends(require_permissions("tills.read"))],
)
async def list_tills(session: DbSession):
    tills = await session.scalars(select(Till).order_by(Till.name))
    return ApiResponse[list[TillRead]](data=[TillRead.model_validate(till) for till in tills])


@router.post(
    "",
    summary="Crear caja",
    response_model=ApiResponse[TillRead],
    status_code=201,
    dependencies=[Depends(require_permissions("tills.create"))],
)
async def create_till(data: TillCreate, session: DbSession):
    till = Till(**data.model_dump())
    session.add(till)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Ya existe una caja con ese nombre.") from exc
    return ApiResponse[TillRead](data=TillRead.model_validate(till))


@router.get(
    "/concepts",
    summary="Listar conceptos de caja",
    response_model=ApiResponse[list[ConceptRead]],
    dependencies=[Depends(require_permissions("till_concepts.read"))],
)
async def list_concepts(session: DbSession):
    concepts = await session.scalars(select(TillConcept).order_by(TillConcept.name))
    return ApiResponse[list[ConceptRead]](
        data=[ConceptRead.model_validate(concept) for concept in concepts]
    )


@router.post(
    "/concepts",
    summary="Crear concepto de caja",
    response_model=ApiResponse[ConceptRead],
    status_code=201,
    dependencies=[Depends(require_permissions("till_concepts.create"))],
)
async def create_concept(data: ConceptCreate, session: DbSession):
    concept = TillConcept(**data.model_dump())
    session.add(concept)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Ya existe un concepto con ese código.") from exc
    return ApiResponse[ConceptRead](data=ConceptRead.model_validate(concept))


@router.get(
    "/{till_id}/shifts",
    summary="Listar turnos de una caja",
    response_model=ApiResponse[Page[ShiftRead]],
    dependencies=[Depends(require_permissions("till_shifts.read"))],
)
async def list_shifts(till_id: UUID, session: DbSession, pagination: Pagination):
    if await session.get(Till, till_id) is None:
        raise NotFoundError("Caja no encontrada.")
    scope = TillShift.till_id == till_id
    total = await session.scalar(select(func.count()).select_from(TillShift).where(scope))
    shifts = await session.scalars(
        select(TillShift)
        .where(scope)
        .order_by(TillShift.opened_at.desc(), TillShift.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[ShiftRead]](
        data=Page[ShiftRead].build(
            [ShiftRead.model_validate(shift) for shift in shifts], total or 0, pagination
        )
    )


@router.post(
    "/{till_id}/shifts",
    summary="Abrir turno de caja",
    response_model=ApiResponse[ShiftRead],
    status_code=201,
    dependencies=[Depends(require_permissions("tills.open"))],
)
async def open_shift(
    till_id: UUID, data: ShiftOpen, session: DbSession, user: CurrentUser, key: IdempotencyKey
):
    result = await service.run_operation(
        session,
        key,
        user.id,
        f"open:{till_id}",
        data,
        partial(service.open_shift, session, till_id, user.id, data),
        ShiftRead,
    )
    return ApiResponse[ShiftRead](data=result)


@router.get(
    "/shifts/{shift_id}",
    summary="Consultar turno de caja",
    response_model=ApiResponse[ShiftRead],
    dependencies=[Depends(require_permissions("till_shifts.read"))],
)
async def get_shift(shift_id: UUID, session: DbSession):
    shift = await session.get(TillShift, shift_id)
    if shift is None:
        raise NotFoundError("Turno de caja no encontrado.")
    return ApiResponse[ShiftRead](data=ShiftRead.model_validate(shift))


@router.patch(
    "/shifts/{shift_id}/close",
    summary="Cerrar turno y registrar el arqueo de caja",
    response_model=ApiResponse[ShiftRead],
    dependencies=[Depends(require_permissions("tills.close"))],
)
async def close_shift(
    shift_id: UUID, data: ShiftClose, session: DbSession, user: CurrentUser, key: IdempotencyKey
):
    result = await service.run_operation(
        session,
        key,
        user.id,
        f"close:{shift_id}",
        data,
        partial(service.close_shift, session, shift_id, user.id, data),
        ShiftRead,
    )
    return ApiResponse[ShiftRead](data=result)


@router.get(
    "/shifts/{shift_id}/movements",
    summary="Listar movimientos de caja",
    response_model=ApiResponse[Page[MovementRead]],
    dependencies=[Depends(require_permissions("till_movements.read"))],
)
async def list_movements(shift_id: UUID, session: DbSession, pagination: Pagination):
    if await session.get(TillShift, shift_id) is None:
        raise NotFoundError("Turno de caja no encontrado.")
    scope = TillMovement.shift_id == shift_id
    total = await session.scalar(select(func.count()).select_from(TillMovement).where(scope))
    movements = await session.scalars(
        select(TillMovement)
        .where(scope)
        .order_by(TillMovement.created_at.desc(), TillMovement.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[MovementRead]](
        data=Page[MovementRead].build(
            [MovementRead.model_validate(movement) for movement in movements],
            total or 0,
            pagination,
        )
    )


@router.post(
    "/shifts/{shift_id}/movements",
    summary="Registrar ingreso o egreso de caja",
    response_model=ApiResponse[MovementRead],
    status_code=201,
    dependencies=[Depends(require_permissions("till_movements.create"))],
)
async def record_movement(
    shift_id: UUID, data: MovementCreate, session: DbSession, user: CurrentUser, key: IdempotencyKey
):
    result = await service.run_operation(
        session,
        key,
        user.id,
        f"movement:{shift_id}",
        data,
        partial(service.record_movement, session, shift_id, user.id, data),
        MovementRead,
    )
    return ApiResponse[MovementRead](data=result)


@router.post(
    "/transfers",
    summary="Transferir efectivo entre cajas",
    response_model=ApiResponse[TransferRead],
    status_code=201,
    dependencies=[Depends(require_permissions("tills.transfer"))],
)
async def transfer_cash(
    data: TransferCreate, session: DbSession, user: CurrentUser, key: IdempotencyKey
):
    result = await service.run_operation(
        session,
        key,
        user.id,
        "transfer",
        data,
        partial(service.transfer_cash, session, user.id, data),
        TransferRead,
    )
    return ApiResponse[TransferRead](data=result)


@router.patch(
    "/movements/{movement_id}/void",
    summary="Anular movimiento de caja",
    response_model=ApiResponse[VoidRead],
    dependencies=[Depends(require_permissions("till_movements.void"))],
)
async def void_movement(
    movement_id: UUID,
    data: VoidMovement,
    session: DbSession,
    user: CurrentUser,
    key: IdempotencyKey,
):
    result = await service.run_operation(
        session,
        key,
        user.id,
        f"void:{movement_id}",
        data,
        partial(service.void_movement, session, movement_id, user.id, data),
        VoidRead,
    )
    return ApiResponse[VoidRead](data=result)

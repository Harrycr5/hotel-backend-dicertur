from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from .inventory_router import commit_or_conflict
from .inventory_router import router as inventory_router
from .models import Rate, RoomType
from .schemas import RateCreate, RateRead, RateUpdate, RoomTypeCreate, RoomTypeRead, RoomTypeUpdate

router = APIRouter(prefix="/rooms", tags=["Rooms"])


async def get_type_or_404(session: DbSession, room_type_id: UUID) -> RoomType:
    room_type = await session.get(RoomType, room_type_id)
    if room_type is None:
        raise NotFoundError("Tipo de habitación no encontrado.")
    return room_type


async def get_rate_or_404(session: DbSession, rate_id: UUID) -> Rate:
    rate = await session.get(Rate, rate_id)
    if rate is None:
        raise NotFoundError("Tarifa no encontrada.")
    return rate


async def save_room_type(session: DbSession, room_type: RoomType) -> None:
    name = room_type.name
    room_type_id = room_type.id
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        conflict = select(RoomType.id).where(RoomType.name == name)
        if room_type_id is not None:
            conflict = conflict.where(RoomType.id != room_type_id)
        if await session.scalar(conflict) is not None:
            raise ConflictError("Ya existe un tipo de habitación con ese nombre.") from exc
        raise
    await session.refresh(room_type)


@router.get(
    "/types",
    summary="Listar tipos de habitación",
    response_model=ApiResponse[Page[RoomTypeRead]],
    dependencies=[Depends(require_permissions("room_types.read"))],
)
async def list_room_types(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(RoomType))
    rows = await session.scalars(
        select(RoomType)
        .order_by(RoomType.name, RoomType.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[RoomTypeRead]](
        message="Tipos de habitación obtenidos correctamente.",
        data=Page[RoomTypeRead].build(
            [RoomTypeRead.model_validate(row) for row in rows], total or 0, pagination
        ),
    )


@router.post(
    "/types",
    summary="Crear tipo de habitación",
    response_model=ApiResponse[RoomTypeRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("room_types.create"))],
)
async def create_room_type(data: RoomTypeCreate, session: DbSession):
    room_type = RoomType(**data.model_dump())
    session.add(room_type)
    await save_room_type(session, room_type)
    return ApiResponse[RoomTypeRead](
        message="Tipo de habitación creado correctamente.",
        data=RoomTypeRead.model_validate(room_type),
    )


@router.get(
    "/types/{room_type_id}",
    summary="Consultar tipo de habitación",
    response_model=ApiResponse[RoomTypeRead],
    dependencies=[Depends(require_permissions("room_types.read"))],
)
async def get_room_type(room_type_id: UUID, session: DbSession):
    room_type = await get_type_or_404(session, room_type_id)
    return ApiResponse[RoomTypeRead](
        message="Tipo de habitación obtenido correctamente.",
        data=RoomTypeRead.model_validate(room_type),
    )


@router.patch(
    "/types/{room_type_id}",
    summary="Actualizar tipo de habitación",
    response_model=ApiResponse[RoomTypeRead],
    dependencies=[Depends(require_permissions("room_types.update"))],
)
async def update_room_type(room_type_id: UUID, data: RoomTypeUpdate, session: DbSession):
    room_type = await get_type_or_404(session, room_type_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room_type, field, value)
    await save_room_type(session, room_type)
    return ApiResponse[RoomTypeRead](
        message="Tipo de habitación actualizado correctamente.",
        data=RoomTypeRead.model_validate(room_type),
    )


@router.delete(
    "/types/{room_type_id}",
    summary="Eliminar tipo de habitación",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("room_types.delete"))],
)
async def delete_room_type(room_type_id: UUID, session: DbSession) -> None:
    await session.delete(await get_type_or_404(session, room_type_id))
    await commit_or_conflict(session, "El tipo está asignado a una habitación.")


@router.get(
    "/rates",
    summary="Listar tarifas",
    response_model=ApiResponse[Page[RateRead]],
    dependencies=[Depends(require_permissions("room_rates.read"))],
)
async def list_rates(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(Rate))
    rows = await session.scalars(
        select(Rate)
        .order_by(Rate.name, Rate.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[RateRead]](
        message="Tarifas obtenidas correctamente.",
        data=Page[RateRead].build(
            [RateRead.model_validate(row) for row in rows], total or 0, pagination
        ),
    )


@router.post(
    "/rates",
    summary="Crear tarifa",
    response_model=ApiResponse[RateRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("room_rates.create"))],
)
async def create_rate(data: RateCreate, session: DbSession):
    rate = Rate(**data.model_dump())
    session.add(rate)
    await session.commit()
    await session.refresh(rate)
    return ApiResponse[RateRead](
        message="Tarifa creada correctamente.", data=RateRead.model_validate(rate)
    )


@router.get(
    "/rates/{rate_id}",
    summary="Consultar tarifa",
    response_model=ApiResponse[RateRead],
    dependencies=[Depends(require_permissions("room_rates.read"))],
)
async def get_rate(rate_id: UUID, session: DbSession):
    rate = await get_rate_or_404(session, rate_id)
    return ApiResponse[RateRead](
        message="Tarifa obtenida correctamente.", data=RateRead.model_validate(rate)
    )


@router.patch(
    "/rates/{rate_id}",
    summary="Actualizar tarifa",
    response_model=ApiResponse[RateRead],
    dependencies=[Depends(require_permissions("room_rates.update"))],
)
async def update_rate(rate_id: UUID, data: RateUpdate, session: DbSession):
    rate = await get_rate_or_404(session, rate_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rate, field, value)
    await session.commit()
    await session.refresh(rate)
    return ApiResponse[RateRead](
        message="Tarifa actualizada correctamente.", data=RateRead.model_validate(rate)
    )


@router.delete(
    "/rates/{rate_id}",
    summary="Eliminar tarifa",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("room_rates.delete"))],
)
async def delete_rate(rate_id: UUID, session: DbSession) -> None:
    await session.delete(await get_rate_or_404(session, rate_id))
    await commit_or_conflict(session, "La tarifa está asignada a una habitación.")


catalog_router = router
router = APIRouter()
router.include_router(catalog_router)
router.include_router(inventory_router, tags=["Rooms"])

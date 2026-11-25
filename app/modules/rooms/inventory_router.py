from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, undefer
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from .choices import RoomStatus
from .images import convert_photo_to_webp
from .models import Floor, Rate, Room, RoomCategory, RoomImage, RoomType
from .schemas import (
    FloorCreate,
    FloorRead,
    RoomCategoryRead,
    RoomCreate,
    RoomImageRead,
    RoomRead,
    RoomStatusChoice,
    RoomUpdate,
)

router = APIRouter()
admin = APIRouter(prefix="/rooms")
room_query = select(Room).options(selectinload(Room.rates), selectinload(Room.images))
max_photo_bytes = 5 * 1024 * 1024


async def commit_or_conflict(session: DbSession, message: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(message) from exc


async def get_floor_or_404(session: DbSession, floor_id: UUID) -> Floor:
    floor = await session.get(Floor, floor_id)
    if floor is None:
        raise NotFoundError("Piso no encontrado.")
    return floor


async def get_room_or_404(session: DbSession, room_id: UUID, *, lock: bool = False) -> Room:
    query = room_query.where(Room.id == room_id)
    room = await session.scalar(query.with_for_update() if lock else query)
    if room is None:
        raise NotFoundError("Habitación no encontrada.")
    return room


async def get_rates(session: DbSession, rate_ids: list[UUID]) -> list[Rate]:
    if not rate_ids:
        return []
    rates = (await session.scalars(select(Rate).where(Rate.id.in_(rate_ids)))).all()
    if len(rates) != len(set(rate_ids)):
        raise NotFoundError("Una o más tarifas no existen.")
    return list(rates)


async def validate_room_type(session: DbSession, room_type_id: UUID) -> None:
    if await session.get(RoomType, room_type_id) is None:
        raise NotFoundError("Tipo de habitación no encontrado.")


async def validate_room_category(session: DbSession, category_id: UUID | None) -> None:
    if category_id is not None and await session.get(RoomCategory, category_id) is None:
        raise NotFoundError("Categoría de habitación no encontrada.")


@admin.get(
    "/floors",
    summary="Listar pisos",
    response_model=ApiResponse[Page[FloorRead]],
    dependencies=[Depends(require_permissions("room_floors.read"))],
)
async def list_floors(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(Floor))
    floors = await session.scalars(
        select(Floor)
        .order_by(Floor.created_at, Floor.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[FloorRead]](
        data=Page[FloorRead].build(
            [FloorRead.model_validate(floor) for floor in floors], total or 0, pagination
        ),
    )


@admin.post(
    "/floors",
    summary="Crear piso",
    response_model=ApiResponse[FloorRead],
    status_code=201,
    dependencies=[Depends(require_permissions("room_floors.create"))],
)
async def create_floor(data: FloorCreate, session: DbSession):
    floor = Floor(description=data.description)
    session.add(floor)
    await commit_or_conflict(session, "Ya existe un piso con esa descripción.")
    await session.refresh(floor)
    return ApiResponse[FloorRead](data=FloorRead.model_validate(floor))


@admin.get(
    "/floors/{floor_id}",
    summary="Consultar piso",
    response_model=ApiResponse[FloorRead],
    dependencies=[Depends(require_permissions("room_floors.read"))],
)
async def get_floor(floor_id: UUID, session: DbSession):
    return ApiResponse[FloorRead](
        data=FloorRead.model_validate(await get_floor_or_404(session, floor_id))
    )


@admin.patch(
    "/floors/{floor_id}",
    summary="Actualizar piso",
    response_model=ApiResponse[FloorRead],
    dependencies=[Depends(require_permissions("room_floors.update"))],
)
async def update_floor(floor_id: UUID, data: FloorCreate, session: DbSession):
    floor = await get_floor_or_404(session, floor_id)
    floor.description = data.description
    await commit_or_conflict(session, "Ya existe un piso con esa descripción.")
    await session.refresh(floor)
    return ApiResponse[FloorRead](data=FloorRead.model_validate(floor))


@admin.delete(
    "/floors/{floor_id}",
    summary="Eliminar piso",
    status_code=204,
    dependencies=[Depends(require_permissions("room_floors.delete"))],
)
async def delete_floor(floor_id: UUID, session: DbSession) -> None:
    await session.delete(await get_floor_or_404(session, floor_id))
    await commit_or_conflict(session, "El piso está asignado a una habitación.")


@admin.get(
    "",
    summary="Listar habitaciones",
    response_model=ApiResponse[Page[RoomRead]],
    dependencies=[Depends(require_permissions("rooms.read"))],
)
async def list_rooms(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(Room))
    rooms = await session.scalars(
        room_query.order_by(Room.code, Room.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[RoomRead]](
        data=Page[RoomRead].build(
            [RoomRead.model_validate(room) for room in rooms], total or 0, pagination
        )
    )


@admin.post(
    "",
    summary="Crear habitación",
    response_model=ApiResponse[RoomRead],
    status_code=201,
    dependencies=[Depends(require_permissions("rooms.create"))],
)
async def create_room(data: RoomCreate, session: DbSession):
    await get_floor_or_404(session, data.floor_id)
    await validate_room_type(session, data.room_type_id)
    await validate_room_category(session, data.category_id)
    rates = await get_rates(session, data.rate_ids)
    room = Room(**data.model_dump(exclude={"rate_ids"}), rates=rates, images=[])
    session.add(room)
    await commit_or_conflict(
        session, "El código ya existe o alguna referencia dejó de estar disponible."
    )
    room = await get_room_or_404(session, room.id)
    return ApiResponse[RoomRead](data=RoomRead.model_validate(room))


@admin.get(
    "/categories",
    summary="Listar categorías de habitación",
    response_model=ApiResponse[list[RoomCategoryRead]],
    dependencies=[Depends(require_permissions("room_categories.read"))],
)
async def list_room_categories(session: DbSession):
    categories = await session.scalars(select(RoomCategory).order_by(RoomCategory.name))
    return ApiResponse[list[RoomCategoryRead]](
        data=[RoomCategoryRead.model_validate(category) for category in categories]
    )


@admin.get(
    "/statuses",
    summary="Listar estados de habitación",
    response_model=ApiResponse[list[RoomStatusChoice]],
    dependencies=[Depends(require_permissions("rooms.read"))],
)
async def list_room_statuses():
    return ApiResponse[list[RoomStatusChoice]](
        data=[RoomStatusChoice(value=option, label=option.label) for option in RoomStatus]
    )


@admin.get(
    "/{room_id}",
    summary="Consultar habitación",
    response_model=ApiResponse[RoomRead],
    dependencies=[Depends(require_permissions("rooms.read"))],
)
async def get_room(room_id: UUID, session: DbSession):
    return ApiResponse[RoomRead](
        data=RoomRead.model_validate(await get_room_or_404(session, room_id))
    )


@admin.patch(
    "/{room_id}",
    summary="Actualizar habitación",
    response_model=ApiResponse[RoomRead],
    dependencies=[Depends(require_permissions("rooms.update"))],
)
async def update_room(room_id: UUID, data: RoomUpdate, session: DbSession):
    room = await get_room_or_404(session, room_id, lock=True)
    if data.floor_id is not None:
        await get_floor_or_404(session, data.floor_id)
    if data.room_type_id is not None:
        await validate_room_type(session, data.room_type_id)
    await validate_room_category(session, data.category_id)
    if "rate_ids" in data.model_fields_set:
        room.rates = await get_rates(session, data.rate_ids)
    for field, value in data.model_dump(exclude_unset=True, exclude={"rate_ids"}).items():
        setattr(room, field, value)
    await commit_or_conflict(
        session, "El código ya existe o alguna referencia dejó de estar disponible."
    )
    room = await get_room_or_404(session, room_id)
    return ApiResponse[RoomRead](data=RoomRead.model_validate(room))


@admin.delete(
    "/{room_id}",
    summary="Eliminar habitación",
    status_code=204,
    dependencies=[Depends(require_permissions("rooms.delete"))],
)
async def delete_room(room_id: UUID, session: DbSession) -> None:
    await session.delete(await get_room_or_404(session, room_id, lock=True))
    await session.commit()


@admin.post(
    "/{room_id}/images",
    summary="Subir foto de una habitación",
    response_model=ApiResponse[RoomImageRead],
    status_code=201,
    dependencies=[Depends(require_permissions("room_images.create"))],
)
async def upload_room_image(room_id: UUID, file: UploadFile, session: DbSession):
    content = await file.read(max_photo_bytes + 1)
    if len(content) > max_photo_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La foto supera los 5 MiB.")
    webp = await run_in_threadpool(convert_photo_to_webp, content)
    await get_room_or_404(session, room_id, lock=True)
    image = RoomImage(room_id=room_id, content_type="image/webp", content=webp)
    session.add(image)
    await session.commit()
    return ApiResponse[RoomImageRead](data=RoomImageRead.model_validate(image))


@router.get(
    "/rooms/{room_id}/images/{image_id}",
    summary="Ver foto de una habitación",
    response_class=Response,
)
async def get_room_image(room_id: UUID, image_id: UUID, session: DbSession):
    image = await session.scalar(
        select(RoomImage)
        .join(Room, RoomImage.room_id == Room.id)
        .options(undefer(RoomImage.content))
        .where(Room.id == room_id, Room.visible.is_(True), RoomImage.id == image_id)
    )
    if image is None:
        raise NotFoundError("Foto no encontrada.")
    return Response(
        content=image.content,
        media_type=image.content_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@admin.delete(
    "/{room_id}/images/{image_id}",
    summary="Eliminar foto de una habitación",
    status_code=204,
    dependencies=[Depends(require_permissions("room_images.delete"))],
)
async def delete_room_image(room_id: UUID, image_id: UUID, session: DbSession) -> None:
    image = await session.scalar(
        select(RoomImage).where(RoomImage.room_id == room_id, RoomImage.id == image_id)
    )
    if image is None:
        raise NotFoundError("Foto no encontrada.")
    await session.delete(image)
    await session.commit()


router.include_router(admin)

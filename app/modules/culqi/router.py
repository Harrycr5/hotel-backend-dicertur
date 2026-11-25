from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.api.dependencies import DbSession
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from . import service
from .schemas import AuthenticateCharge, ChargeCreate, ChargeRead, ReconcileCharge

router = APIRouter(prefix="/culqi", tags=["Culqi"])
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=100, pattern=r"^[!-~]+$")
]


@router.post(
    "/charges",
    summary="Crear cargo en Culqi",
    response_model=ApiResponse[ChargeRead],
    status_code=201,
    dependencies=[Depends(require_permissions("culqi.charge"))],
)
async def create_charge(data: ChargeCreate, session: DbSession, key: IdempotencyKey):
    charge = await service.create_charge(session, key, data)
    return ApiResponse[ChargeRead](data=ChargeRead.model_validate(charge))


@router.get(
    "/charges/{charge_id}",
    summary="Consultar cargo de Culqi",
    response_model=ApiResponse[ChargeRead],
    dependencies=[Depends(require_permissions("culqi.read"))],
)
async def get_charge(charge_id: UUID, session: DbSession):
    charge = await service.get_charge(session, charge_id)
    return ApiResponse[ChargeRead](data=ChargeRead.model_validate(charge))


@router.post(
    "/charges/{charge_id}/authenticate",
    summary="Autenticar cargo de Culqi con 3DS",
    response_model=ApiResponse[ChargeRead],
    dependencies=[Depends(require_permissions("culqi.charge"))],
)
async def authenticate_charge(charge_id: UUID, data: AuthenticateCharge, session: DbSession):
    charge = await service.authenticate_charge(session, charge_id, data)
    return ApiResponse[ChargeRead](data=ChargeRead.model_validate(charge))


@router.post(
    "/charges/{charge_id}/reconcile",
    summary="Conciliar cargo de Culqi",
    response_model=ApiResponse[ChargeRead],
    dependencies=[Depends(require_permissions("culqi.reconcile"))],
)
async def reconcile_charge(charge_id: UUID, data: ReconcileCharge, session: DbSession):
    charge = await service.reconcile_charge(session, charge_id, data.provider_charge_id)
    return ApiResponse[ChargeRead](data=ChargeRead.model_validate(charge))

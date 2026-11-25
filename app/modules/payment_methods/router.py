from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from .models import PaymentMethod

router = APIRouter(prefix="/payment-methods", tags=["Payment methods"])


class PaymentMethodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    is_active: bool


@router.get(
    "",
    summary="Listar métodos de pago",
    response_model=ApiResponse[list[PaymentMethodRead]],
    dependencies=[Depends(require_permissions("payment_methods.read"))],
)
async def list_payment_methods(session: DbSession):
    methods = await session.scalars(select(PaymentMethod).order_by(PaymentMethod.name))
    return ApiResponse[list[PaymentMethodRead]](
        data=[PaymentMethodRead.model_validate(method) for method in methods]
    )

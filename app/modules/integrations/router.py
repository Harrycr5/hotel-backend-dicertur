from fastapi import APIRouter, Depends, Response

from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from .schemas import ReniecLookup, ReniecResponse, SendEmail
from .service import consult_reniec, deliver_email

router = APIRouter(prefix="/integrations", tags=["Integraciones"])


@router.post(
    "/email",
    summary="Enviar correo electrónico",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_permissions("integrations.send_email"))],
)
async def send_email(data: SendEmail):
    await deliver_email(data)
    return ApiResponse[None](message="Correo entregado al servidor SMTP.", data=None)


@router.post(
    "/reniec",
    summary="Consultar datos básicos de un DNI",
    response_model=ReniecResponse,
    responses={
        502: {"description": "Falló la comunicación con Scrall o su respuesta fue inválida."}
    },
    dependencies=[Depends(require_permissions("integrations.lookup_dni"))],
)
async def lookup_dni(data: ReniecLookup, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return ReniecResponse(data=await consult_reniec(data.dni))

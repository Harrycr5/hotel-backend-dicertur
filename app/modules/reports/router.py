from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import DbSession
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from .choices import ReportMonth
from .guest_register import generate_guest_register
from .schemas import ReportMonthRead, ReportPeriod
from .service import generate_report

XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(require_permissions("reports.export"))],
)


@router.get(
    "/months",
    summary="Listar meses para los reportes",
    response_model=ApiResponse[list[ReportMonthRead]],
)
async def list_months():
    return ApiResponse[list[ReportMonthRead]](
        data=[ReportMonthRead(value=month, label=month.label) for month in ReportMonth]
    )


@router.get(
    "/dircetur",
    summary="Descargar reporte DIRCETUR",
    response_class=Response,
    responses={
        200: {"content": {XLSX_MIME_TYPE: {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def download_dircetur(period: Annotated[ReportPeriod, Query()], session: DbSession):
    content = await generate_report(session, period)
    filename = f"reporte-dircetur-{period.year}-{int(period.month):02}.xlsx"
    return xlsx_download(content, filename)


@router.get(
    "/guest-register",
    summary="Descargar registro mensual de huéspedes",
    response_class=Response,
    dependencies=[Depends(require_permissions("reports.guests_export"))],
    responses={
        200: {"content": {XLSX_MIME_TYPE: {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def download_guest_register(period: Annotated[ReportPeriod, Query()], session: DbSession):
    content = await generate_guest_register(session, period)
    filename = f"registro-huespedes-{period.year}-{int(period.month):02}.xlsx"
    return xlsx_download(content, filename)


def xlsx_download(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type=XLSX_MIME_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )

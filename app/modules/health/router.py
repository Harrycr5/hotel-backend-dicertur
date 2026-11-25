from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Comprobar el estado de la API")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

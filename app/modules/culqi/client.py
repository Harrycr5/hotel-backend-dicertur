import httpx
from fastapi import HTTPException

from app.core.config import get_settings

API_BASE = "https://api.culqi.com/v2"


def api_key() -> str:
    settings = get_settings()
    key = settings.culqi_secret_key
    value = key.get_secret_value() if key else ""
    if value.startswith("sk_test_") or (value.startswith("sk_live_") and settings.culqi_allow_live):
        return value
    raise HTTPException(503, "Culqi no está habilitado para este entorno.")


async def request(method: str, path: str, key: str, payload: dict | None = None):
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.request(
                method,
                f"{API_BASE}{path}",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        body = response.json()
        return response.status_code, body if isinstance(body, dict) else {}
    except (httpx.RequestError, ValueError):
        return 0, {}

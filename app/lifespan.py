import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .db.session import engine
from .modules.reservations.service import run_reservation_expiration


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    expiration = asyncio.create_task(run_reservation_expiration())
    try:
        yield
    finally:
        expiration.cancel()
        with suppress(asyncio.CancelledError):
            await expiration
        await engine.dispose()

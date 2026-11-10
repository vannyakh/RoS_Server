"""Server status and local configuration file."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_db
from app.infrastructure.storage import CONFIGURATIONS

router = APIRouter(tags=["Health"])
SERVER_VERSION = "2.0.0"


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable", "version": SERVER_VERSION},
        )
    return {"status": "ready", "database": "ok", "version": SERVER_VERSION}


@router.get("/version.cfg")
async def version_cfg() -> FileResponse:
    return FileResponse(CONFIGURATIONS / "version.cfg", media_type="text/plain")

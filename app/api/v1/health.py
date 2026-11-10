"""Server status and local configuration file."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.infrastructure.storage import CONFIGURATIONS

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/version.cfg")
async def version_cfg() -> FileResponse:
    return FileResponse(CONFIGURATIONS / "version.cfg", media_type="text/plain")

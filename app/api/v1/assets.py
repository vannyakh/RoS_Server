"""Asset library routes. Reads are public so <img> tags work; writes need assets.manage."""

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import current_operator
from app.infrastructure.database import get_db
from app.schemas.common import Page
from app.services.asset_service import MAX_MODEL_BYTES, AssetService
from app.services.operator_service import OperatorActor

public = APIRouter(prefix="/assets", tags=["Assets"])
admin = APIRouter(prefix="/admin/assets", tags=["Assets"])

KIND = "^(rank|prop|item|character|currency|badge|other|model)$"
KEY = "^[A-Za-z0-9_.-]{1,64}$"


@public.get("/{kind}/{key}")
async def asset_file(
    kind: str = Path(pattern=KIND),
    key: str = Path(pattern=KEY),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row, data = await AssetService(db).file(kind, key)
    return Response(
        content=data,
        media_type=row.content_type,
        headers={
            # URLs carry ?v=<hash>, so a replaced image gets a new URL.
            "Cache-Control": "public, max-age=86400",
            "ETag": f'"{row.sha256}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )


@admin.get("", response_model=Page[dict])
async def list_assets(
    kind: str | None = Query(default=None, pattern=KIND),
    q: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> Page[dict]:
    items, total = await AssetService(db).listing(kind, q, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@admin.post("", status_code=201)
async def upload_asset(
    kind: str = Form(pattern=KIND),
    key: str = Form(pattern=KEY),
    name: str = Form(default="", max_length=80),
    source: str = Form(default="", max_length=240),
    upload: UploadFile = File(),
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # The service applies the per-kind limit; read at most one byte past the largest.
    data = await upload.read(MAX_MODEL_BYTES + 1)
    return await AssetService(db).upload(actor, kind, key, name, source, data)


@admin.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: str,
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> None:
    await AssetService(db).delete(actor, asset_id)

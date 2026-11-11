"""Published map catalog. Drafts are not listed here."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_db
from app.schemas.common import Page
from app.schemas.maps import ManifestResponse, MapDetail, MapSummary, MapVersionSummary
from app.services.maps.catalog import MapService
from app.services.maps.validation import COORDINATE_SYSTEM

router = APIRouter(prefix="/maps", tags=["Maps"])


def _summary(definition, version, size: int) -> MapSummary:
    return MapSummary(
        id=definition.id,
        slug=definition.code,
        name=definition.name,
        description=definition.description,
        current_version=version.version,
        manifest_hash=version.manifest_hash or "",
        download_size_bytes=size,
    )


@router.get("", response_model=Page[MapSummary])
async def maps(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Page[MapSummary]:
    rows, total = await MapService(db).catalog(limit, offset)
    return Page(items=[_summary(*row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/{map_id}", response_model=MapDetail)
async def map_detail(map_id: str, db: AsyncSession = Depends(get_db)) -> MapDetail:
    definition, version, size = await MapService(db).public_definition(map_id)
    summary = _summary(definition, version, size)
    return MapDetail(
        **summary.model_dump(),
        width=definition.width,
        height=definition.height,
        coordinate_system=COORDINATE_SYSTEM,
        origin=[version.origin_x, version.origin_y, version.origin_z],
        size=[version.size_x, version.size_y, version.size_z],
    )


@router.get("/{map_id}/versions", response_model=list[MapVersionSummary])
async def map_versions(map_id: str, db: AsyncSession = Depends(get_db)) -> list[MapVersionSummary]:
    rows = await MapService(db).public_versions(map_id)
    return [MapVersionSummary.model_validate(row, from_attributes=True) for row in rows]


@router.get("/{map_id}/manifest", response_model=ManifestResponse)
async def map_manifest(
    map_id: str,
    version: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ManifestResponse:
    return ManifestResponse.model_validate(await MapService(db).public_manifest(map_id, version))


@router.get("/{map_id}/assets/{asset_id}")
async def map_asset(map_id: str, asset_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    asset, data = await MapService(db).public_asset(map_id, asset_id)
    name = asset.relative_path.replace("\\", "/").split("/")[-1]
    return Response(
        content=data,
        media_type=asset.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )

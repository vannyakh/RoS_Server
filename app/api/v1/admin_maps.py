"""Publisher-only map drafts. The allowed usernames come from MAP_PUBLISHERS."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_account
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.infrastructure.database import get_db
from app.models.account import Account
from app.schemas.game_data import MapDefinitionResponse
from app.schemas.maps import (
    MapAssetResponse,
    MapCreate,
    MapPin,
    MapPublish,
    MapUpdate,
    MapVersionCreate,
    MapVersionSummary,
)
from app.services.maps.catalog import MapService

router = APIRouter(prefix="/admin/maps", tags=["Map administration"])


async def current_publisher(account: Account = Depends(current_account)) -> Account:
    allowed = {item.strip().casefold() for item in get_settings().map_publishers.split(",") if item.strip()}
    if account.status != "active" or account.username not in allowed:
        raise AppError(403, "Map publishing is not allowed")
    return account


@router.post("", response_model=MapDefinitionResponse, status_code=201)
async def create_map(
    body: MapCreate,
    _publisher: Account = Depends(current_publisher),
    db: AsyncSession = Depends(get_db),
) -> MapDefinitionResponse:
    created = await MapService(db).create_definition(body.code, body.name, body.description, body.width, body.height)
    return MapDefinitionResponse.model_validate(created, from_attributes=True)


@router.patch("/{map_id}", response_model=MapDefinitionResponse)
async def update_map(
    map_id: str,
    body: MapUpdate,
    _publisher: Account = Depends(current_publisher),
    db: AsyncSession = Depends(get_db),
) -> MapDefinitionResponse:
    updated = await MapService(db).update_definition(map_id, body.name, body.description, body.width, body.height)
    return MapDefinitionResponse.model_validate(updated, from_attributes=True)


@router.post("/{map_id}/versions", response_model=MapVersionSummary, status_code=201)
async def create_version(
    map_id: str,
    body: MapVersionCreate,
    _publisher: Account = Depends(current_publisher),
    db: AsyncSession = Depends(get_db),
) -> MapVersionSummary:
    created = await MapService(db).create_version(map_id, body.model_dump())
    return MapVersionSummary.model_validate(created, from_attributes=True)


@router.post("/{map_id}/assets", response_model=MapAssetResponse, status_code=201)
async def register_asset(
    map_id: str,
    version_id: str = Form(),
    asset_type: str = Form(),
    relative_path: str = Form(),
    upload: UploadFile = File(),
    _publisher: Account = Depends(current_publisher),
    db: AsyncSession = Depends(get_db),
) -> MapAssetResponse:
    data = await upload.read()
    created = await MapService(db).register_asset(
        map_id,
        version_id,
        asset_type,
        relative_path,
        upload.content_type or "application/octet-stream",
        data,
    )
    return MapAssetResponse.model_validate(created, from_attributes=True)


@router.post("/{map_id}/publish", response_model=MapVersionSummary)
async def publish_map(
    map_id: str,
    body: MapPublish,
    publisher: Account = Depends(current_publisher),
    db: AsyncSession = Depends(get_db),
) -> MapVersionSummary:
    published = await MapService(db).publish(map_id, body.version_id, publisher)
    return MapVersionSummary.model_validate(published, from_attributes=True)


@router.post("/{map_id}/pin", status_code=204)
async def pin_map(
    map_id: str,
    body: MapPin,
    _publisher: Account = Depends(current_publisher),
    db: AsyncSession = Depends(get_db),
) -> None:
    await MapService(db).pin_match(map_id, body.version_id, body.match_id)

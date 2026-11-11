"""Map catalog, drafts, and publication. Routes call this service and do not commit."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.infrastructure.map_storage import DEFAULT_ROOT, MapStorage
from app.models.account import Account
from app.models.game_data import MapDefinition
from app.models.map_content import (
    MapAsset,
    MapObject,
    MapPointOfInterest,
    MapPublication,
    MapRegion,
    MapSpawnPoint,
    MapVersion,
)
from app.repositories.map_repository import MapRepository
from app.services.maps.manifest import manifest_body, with_hash
from app.services.maps.publishing import verified_manifest
from app.services.maps.validation import (
    require_asset_type,
    require_bytes,
    require_code,
    require_finite,
    require_inside,
    require_relative_path,
    require_scale,
    require_version,
    sha256_hex,
)
from app.services.maps.versioning import require_draft


def storage_for_settings() -> MapStorage:
    configured = get_settings().map_storage_dir.strip()
    if not configured:
        return MapStorage(DEFAULT_ROOT)
    path = Path(configured)
    if not path.is_absolute():
        path = DEFAULT_ROOT.parent.parent / path
    return MapStorage(path)


class MapService:
    def __init__(self, session: AsyncSession, storage: MapStorage | None = None) -> None:
        self.session = session
        self.maps = MapRepository(session)
        self.storage = storage or storage_for_settings()

    async def create_definition(self, code: str, name: str, description: str, width: int, height: int) -> MapDefinition:
        require_code(code, "Slug")
        if width < 1 or height < 1:
            raise AppError(422, "Map dimensions must be at least 1")
        row = MapDefinition(code=code, name=name, description=description, width=width, height=height, is_active=True)
        self.session.add(row)
        await self._commit("Map slug already exists")
        await self.session.refresh(row)
        return row

    async def update_definition(self, map_id: str, name: str | None, description: str | None, width: int | None, height: int | None) -> MapDefinition:
        row = await self._definition(map_id)
        published = await self.maps.latest_published(map_id)
        if published is not None and (width is not None or height is not None):
            raise AppError(409, "Published map dimensions are immutable")
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if width is not None:
            row.width = width
        if height is not None:
            row.height = height
        await self._commit()
        await self.session.refresh(row)
        return row

    async def create_version(self, map_id: str, payload: dict) -> MapVersion:
        definition = await self._definition(map_id)
        version_name = require_version(payload["version"])
        if int(payload["schema_version"]) != 1:
            raise AppError(422, "Unsupported map schema version")
        origin = _vec(payload["origin"], "origin")
        size = _vec(payload["size"], "size")
        if any(value <= 0 for value in size):
            raise AppError(422, "Map size must be greater than zero")
        version = MapVersion(
            map_id=definition.id,
            version=version_name,
            schema_version=1,
            engine_profile=payload["engine_profile"],
            status="draft",
            origin_x=origin[0],
            origin_y=origin[1],
            origin_z=origin[2],
            size_x=size[0],
            size_y=size[1],
            size_z=size[2],
        )
        self.session.add(version)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, "Map version already exists") from exc
        self._add_children(version, origin, size, payload)
        await self._commit()
        return await self._loaded(version.id)

    async def register_asset(self, map_id: str, version_id: str, asset_type: str, relative_path: str, mime_type: str, data: bytes) -> MapAsset:
        version = await self._owned_version(map_id, version_id)
        require_draft(version)
        asset_type = require_asset_type(asset_type)
        relative_path = require_relative_path(relative_path)
        data = require_bytes(data)
        digest = sha256_hex(data)
        existing = next((asset for asset in version.assets if asset.relative_path == relative_path), None)
        if existing is not None:
            if existing.sha256 != digest:
                raise AppError(409, "Asset path already registered")
            return existing
        key = f"maps/{map_id}/{version.version}/{relative_path}"
        self.storage.write_new(key, data)
        asset = MapAsset(
            map_version_id=version.id,
            asset_type=asset_type,
            relative_path=relative_path,
            storage_key=key,
            mime_type=mime_type or "application/octet-stream",
            size_bytes=len(data),
            sha256=digest,
            details={},
        )
        self.session.add(asset)
        await self._commit("Asset path already registered")
        await self.session.refresh(asset)
        return asset

    async def publish(self, map_id: str, version_id: str, account: Account) -> MapVersion:
        version = await self._owned_version(map_id, version_id)
        if version.status == "published":
            raise AppError(409, "Map version is already published")
        require_draft(version)
        definition = await self._definition(map_id)
        signed = verified_manifest(version, definition.code, list(version.assets), self.storage)
        version.manifest_hash = signed["manifest_hash"]
        version.status = "published"
        version.published_at = datetime.now(timezone.utc)
        version.publisher_account_id = account.id
        self.session.add(MapPublication(map_version_id=version.id, published_at=version.published_at, published_by=account.id))
        await self._commit()
        return await self._loaded(version.id)

    async def pin_match(self, map_id: str, version_id: str, match_id: str) -> None:
        version = await self._owned_version(map_id, version_id)
        if version.status != "published" or not version.manifest_hash:
            raise AppError(409, "Only a published map version can be pinned")
        match = await self.maps.match(match_id)
        if match is None:
            raise AppError(404, "Match not found")
        match.map_id = map_id
        match.map_version_id = version.id
        match.manifest_hash = version.manifest_hash
        await self._commit()

    async def catalog(self, limit: int, offset: int) -> tuple[list[tuple[MapDefinition, MapVersion, int]], int]:
        rows, total = await self.maps.published_page(limit, offset)
        items: list[tuple[MapDefinition, MapVersion, int]] = []
        for row in rows:
            version = await self.maps.latest_published(row.id)
            if version is None:
                continue
            loaded = await self._loaded(version.id)
            items.append((row, loaded, sum(asset.size_bytes for asset in loaded.assets)))
        return items, total

    async def public_definition(self, map_id: str) -> tuple[MapDefinition, MapVersion, int]:
        definition = await self._definition(map_id)
        version = await self.maps.latest_published(map_id)
        if version is None:
            raise AppError(404, "Map not found")
        loaded = await self._loaded(version.id)
        return definition, loaded, sum(asset.size_bytes for asset in loaded.assets)

    async def public_versions(self, map_id: str) -> list[MapVersion]:
        await self.public_definition(map_id)
        return await self.maps.versions_for(map_id, published_only=True)

    async def public_manifest(self, map_id: str, version_name: str | None) -> dict:
        definition, current, _size = await self.public_definition(map_id)
        version = current
        if version_name is not None:
            matches = [item for item in await self.maps.versions_for(map_id, published_only=True) if item.version == version_name]
            if not matches:
                raise AppError(404, "Map version not found")
            version = await self._loaded(matches[0].id)
        body = manifest_body(definition.id, definition.code, version.version, version.schema_version, version.engine_profile, [
            {"asset_id": asset.id, "path": asset.relative_path, "sha256": asset.sha256, "size_bytes": asset.size_bytes, "type": asset.asset_type}
            for asset in version.assets
        ])
        signed = with_hash(body)
        if signed["manifest_hash"] != version.manifest_hash:
            raise AppError(409, "Stored manifest hash does not match the package")
        return signed

    async def public_asset(self, map_id: str, asset_id: str) -> tuple[MapAsset, bytes]:
        asset = await self.maps.asset(asset_id)
        if asset is None:
            raise AppError(404, "Asset not found")
        version = await self.maps.version(asset.map_version_id)
        if version is None or version.map_id != map_id or version.status != "published":
            raise AppError(404, "Asset not found")
        return asset, self.storage.read(asset.storage_key)

    def _add_children(self, version: MapVersion, origin: tuple[float, float, float], size: tuple[float, float, float], payload: dict) -> None:
        seen_objects: set[str] = set()
        seen_spawns: set[str] = set()
        for region in payload["regions"]:
            minimum = _vec(region["minimum"], "region minimum")
            maximum = _vec(region["maximum"], "region maximum")
            require_inside(origin, size, minimum, "Region")
            require_inside(origin, size, maximum, "Region")
            self.session.add(MapRegion(
                map_version_id=version.id,
                code=require_code(region["code"], "Region code"),
                name=region["name"],
                min_x=minimum[0], min_y=minimum[1], min_z=minimum[2],
                max_x=maximum[0], max_y=maximum[1], max_z=maximum[2],
                details={},
            ))
        for item in payload["objects"]:
            code = require_code(item["object_code"], "Object code")
            if code in seen_objects:
                raise AppError(422, "Duplicate object id")
            seen_objects.add(code)
            position = _vec(item["position"], "object position")
            rotation = _vec(item["rotation"], "object rotation")
            scale = _vec(item["scale"], "object scale")
            require_inside(origin, size, position, "Object")
            require_scale(scale)
            self.session.add(MapObject(
                map_version_id=version.id,
                object_code=code,
                definition_code=require_code(item["definition_code"], "Object definition"),
                category=item["category"],
                position_x=position[0], position_y=position[1], position_z=position[2],
                rotation_x=rotation[0], rotation_y=rotation[1], rotation_z=rotation[2],
                scale_x=scale[0], scale_y=scale[1], scale_z=scale[2],
                collision=item["collision"],
                navigation_obstacle=item["navigation_obstacle"],
                interactive=item["interactive"],
                details={},
            ))
        for spawn in payload["spawn_points"]:
            code = require_code(spawn["spawn_code"], "Spawn code")
            if code in seen_spawns:
                raise AppError(422, "Duplicate spawn id")
            seen_spawns.add(code)
            position = _vec(spawn["position"], "spawn position")
            require_inside(origin, size, position, "Spawn point")
            require_finite(spawn["rotation_y"], "spawn rotation")
            self.session.add(MapSpawnPoint(
                map_version_id=version.id,
                spawn_code=code,
                position_x=position[0], position_y=position[1], position_z=position[2],
                rotation_y=spawn["rotation_y"],
                spawn_group=spawn["spawn_group"],
                enabled=spawn["enabled"],
            ))
        for poi in payload["points_of_interest"]:
            position = _vec(poi["position"], "point of interest")
            require_inside(origin, size, position, "Point of interest")
            self.session.add(MapPointOfInterest(
                map_version_id=version.id,
                poi_code=require_code(poi["poi_code"], "Point of interest code"),
                name=poi["name"],
                description=poi["description"],
                position_x=position[0], position_y=position[1], position_z=position[2],
                icon=poi["icon"],
            ))

    async def _definition(self, map_id: str) -> MapDefinition:
        row = await self.maps.definition(map_id)
        if row is None:
            raise AppError(404, "Map not found")
        return row

    async def _owned_version(self, map_id: str, version_id: str) -> MapVersion:
        await self._definition(map_id)
        version = await self._loaded(version_id)
        if version.map_id != map_id:
            raise AppError(404, "Map version not found")
        return version

    async def _loaded(self, version_id: str) -> MapVersion:
        version = await self.maps.version(version_id)
        if version is None:
            raise AppError(404, "Map version not found")
        return version

    async def _commit(self, conflict: str = "Map data conflicts with an existing row") -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, conflict) from exc


def _vec(values: list[float], label: str) -> tuple[float, float, float]:
    if len(values) != 3:
        raise AppError(422, f"{label} must contain three numbers")
    return tuple(require_finite(float(value), label) for value in values)  # type: ignore[return-value]

"""Publication checks. A version is published only after every stored byte matches its hash."""

from app.core.exceptions import AppError
from app.infrastructure.map_storage import MapStorage
from app.models.map_content import MapAsset, MapVersion
from app.services.maps.manifest import manifest_body, with_hash
from app.services.maps.validation import sha256_hex


def file_entries(assets: list[MapAsset]) -> list[dict]:
    return [
        {
            "asset_id": asset.id,
            "path": asset.relative_path,
            "sha256": asset.sha256,
            "size_bytes": asset.size_bytes,
            "type": asset.asset_type,
        }
        for asset in assets
    ]


def verified_manifest(version: MapVersion, code: str, assets: list[MapAsset], storage: MapStorage) -> dict:
    if not assets:
        raise AppError(422, "A map version needs at least one asset")
    for asset in assets:
        data = storage.read(asset.storage_key)
        digest = sha256_hex(data)
        if digest != asset.sha256 or len(data) != asset.size_bytes:
            raise AppError(422, "Asset hash does not match the stored file")
    body = manifest_body(
        version.map_id,
        code,
        version.version,
        version.schema_version,
        version.engine_profile,
        file_entries(assets),
    )
    return with_hash(body)

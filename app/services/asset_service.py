"""Asset library: operators upload display images; anyone can fetch one by kind and key."""

import hashlib
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.infrastructure.map_storage import DEFAULT_ROOT, MapStorage
from app.models.game_asset import ASSET_KINDS, GameAsset
from app.services.operator_service import OperatorActor, OperatorService

MAX_BYTES = 2 * 1024 * 1024
# Binary glTF models: textures are packed inside the file, so they run larger than icons.
MAX_MODEL_BYTES = 25 * 1024 * 1024
GLB = ("model/gltf-binary", "glb")
# Original lobby categories whose entries are 3D objects. Themes, actions and profile frames are not.
MODEL_LOBBY_CATEGORIES = ("firearms", "clothes", "character", "vehicles", "companions")
KEY = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# Raster images only. SVG is refused: served from the API origin it could carry script.
SIGNATURES: tuple[tuple[str, str, bytes], ...] = (
    ("image/png", "png", b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", "jpg", b"\xff\xd8\xff"),
    ("image/gif", "gif", b"GIF8"),
)


def storage() -> MapStorage:
    configured = settings.game_asset_dir.strip()
    return MapStorage(Path(configured) if configured else DEFAULT_ROOT / "icons")


def sniff(data: bytes) -> tuple[str, str]:
    """(content type, extension) from the file's own bytes, not the upload's claim."""
    for content_type, extension, magic in SIGNATURES:
        if data.startswith(magic):
            return content_type, extension
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    # glTF 2.0 binary: magic "glTF", then uint32 version 2, then the total length.
    if len(data) >= 12 and data[:4] == b"glTF" and int.from_bytes(data[4:8], "little") == 2:
        if int.from_bytes(data[8:12], "little") != len(data):
            raise AppError(422, "The .glb file is truncated or has extra bytes")
        return GLB
    raise AppError(415, "Only PNG, JPEG, GIF or WebP images, or binary glTF (.glb) models, are accepted")


def view(row: GameAsset) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "key": row.key,
        "name": row.name,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "source": row.source,
        "url": f"/api/v1/assets/{row.kind}/{row.key}?v={row.sha256[:12]}",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class AssetService:
    def __init__(self, session: AsyncSession, files: MapStorage | None = None) -> None:
        self.session = session
        self.files = files or storage()
        self.operators = OperatorService(session)

    async def upload(
        self, actor: OperatorActor, kind: str, key: str, name: str, source: str, data: bytes
    ) -> dict:
        self.operators._need(actor, "assets.manage")
        if kind not in ASSET_KINDS:
            raise AppError(422, "Unknown asset kind")
        key = key.strip()
        if not KEY.fullmatch(key):
            raise AppError(422, "Key must be 1-64 letters, digits, dot, dash or underscore")
        if not data:
            raise AppError(422, "The file is empty")
        limit = MAX_MODEL_BYTES if kind == "model" else MAX_BYTES
        if len(data) > limit:
            raise AppError(413, "Models are limited to 25 MB" if kind == "model" else "Images are limited to 2 MB")
        content_type, extension = sniff(data)
        if (kind == "model") != ((content_type, extension) == GLB):
            raise AppError(415, "The model kind takes .glb files only, and .glb files go in the model kind")
        digest = hashlib.sha256(data).hexdigest()
        storage_key = f"{digest[:2]}/{digest}.{extension}"
        if not self.files.resolve(storage_key).exists():
            self.files.write_new(storage_key, data)
        row = await self.session.scalar(select(GameAsset).where(GameAsset.kind == kind, GameAsset.key == key))
        replaced = row is not None
        previous = (row.sha256, row.storage_key) if row is not None else None
        if row is None:
            row = GameAsset(kind=kind, key=key)
            self.session.add(row)
        row.name = name.strip()[:80]
        row.source = source.strip()[:240]
        row.content_type = content_type
        row.size_bytes = len(data)
        row.sha256 = digest
        row.storage_key = storage_key
        row.uploaded_by = actor.operator.id
        await self.session.flush()
        await self.operators._audit(
            actor, "asset.replace" if replaced else "asset.upload", "game_asset", row.id, f"{kind}/{key}", row.source
        )
        await self.session.commit()
        if previous is not None and previous[0] != digest:
            await self._drop_if_unused(*previous)
        return view(row)

    async def listing(self, kind: str | None, query: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
        listed = select(GameAsset)
        counted = select(func.count()).select_from(GameAsset)
        if kind:
            listed = listed.where(GameAsset.kind == kind)
            counted = counted.where(GameAsset.kind == kind)
        if query and query.strip():
            pattern = f"%{query.strip().casefold()}%"
            matched = func.lower(GameAsset.key).like(pattern) | func.lower(GameAsset.name).like(pattern)
            listed = listed.where(matched)
            counted = counted.where(matched)
        rows = list(await self.session.scalars(listed.order_by(GameAsset.kind, GameAsset.key).limit(limit).offset(offset)))
        return [view(row) for row in rows], int(await self.session.scalar(counted) or 0)

    async def model_status(self) -> dict:
        """Which game objects have a 3D model in the library, and which uploads match none.

        A model is looked up by key: `item-<item id>`, `weapon-<weapon code>`, `skin-<skin code>`,
        `prop-<original battle prop id>` or `lobby-<original lobby item id>`. Lobby items are listed
        only for the categories that are 3D objects (MODEL_LOBBY_CATEGORIES).
        """
        from app.api.v1.original_catalog import _lobby, _props
        from app.models.game_data import ItemDefinition
        from app.models.weapon_balance import WeaponBalance
        from app.services.cosmetics_service import SKINS

        models = {row.key: row for row in await self.session.scalars(select(GameAsset).where(GameAsset.kind == "model"))}
        targets: list[tuple[str, str, str, str, str]] = []  # key, type, code, label, detail
        for item in await self.session.scalars(select(ItemDefinition).order_by(ItemDefinition.name)):
            targets.append((f"item-{item.id}", "item", item.code, item.name, item.category))
        for weapon in await self.session.scalars(select(WeaponBalance).order_by(WeaponBalance.weapon_class, WeaponBalance.name)):
            targets.append((f"weapon-{weapon.code}", "weapon", weapon.code, weapon.name, weapon.weapon_class))
        for skin in SKINS:
            targets.append((f"skin-{skin.code}", "skin", skin.code, skin.name, "skin"))
        for prop in _props():
            targets.append((f"prop-{prop['id']}", "prop", str(prop["id"]), prop["name"] or f"Prop {prop['id']}", prop["type"]))
        for entry in _lobby()["items"]:
            if entry["category"] in MODEL_LOBBY_CATEGORIES:
                label = entry["name"] or f"Lobby item {entry['id']}"
                targets.append((f"lobby-{entry['id']}", "lobby", str(entry["id"]), label, entry["category"]))

        rows: list[dict] = []
        by_type: dict[str, dict[str, int]] = {kind: {"total": 0, "ready": 0} for kind in ("item", "weapon", "skin", "prop", "lobby")}
        for key, kind, code, label, detail in targets:
            asset = models.pop(key, None)
            by_type[kind]["total"] += 1
            if asset is not None:
                by_type[kind]["ready"] += 1
            rows.append(
                {
                    "key": key,
                    "type": kind,
                    "code": code,
                    "label": label,
                    "detail": detail,
                    "status": "ready" if asset is not None else "missing",
                    "size_bytes": asset.size_bytes if asset is not None else 0,
                    "updated_at": asset.updated_at if asset is not None else None,
                    "url": view(asset)["url"] if asset is not None else None,
                }
            )
        for key, asset in sorted(models.items()):
            rows.append(
                {
                    "key": key,
                    "type": "other",
                    "code": key,
                    "label": asset.name or key,
                    "detail": "no item, weapon or skin uses this key",
                    "status": "unlinked",
                    "size_bytes": asset.size_bytes,
                    "updated_at": asset.updated_at,
                    "url": view(asset)["url"],
                }
            )
        ready = sum(value["ready"] for value in by_type.values())
        total = sum(value["total"] for value in by_type.values())
        return {
            "summary": {
                "targets": total,
                "ready": ready,
                "missing": total - ready,
                "unlinked": len(models),
                "bytes": sum(row["size_bytes"] for row in rows),
                "by_type": by_type,
            },
            "items": rows,
        }

    async def delete(self, actor: OperatorActor, asset_id: str) -> None:
        self.operators._need(actor, "assets.manage")
        row = await self.session.get(GameAsset, asset_id)
        if row is None:
            raise AppError(404, "Asset was not found")
        await self.operators._audit(actor, "asset.delete", "game_asset", row.id, f"{row.kind}/{row.key}")
        sha256, storage_key = row.sha256, row.storage_key
        await self.session.delete(row)
        await self.session.commit()
        await self._drop_if_unused(sha256, storage_key)

    async def _drop_if_unused(self, sha256: str, storage_key: str) -> None:
        """Files are content-addressed; keep a file another row still points at."""
        still_used = await self.session.scalar(select(func.count()).select_from(GameAsset).where(GameAsset.sha256 == sha256))
        if not still_used:
            self.files.resolve(storage_key).unlink(missing_ok=True)

    async def url_for(self, kind: str, key: str) -> str | None:
        """Store path of one asset (with its cache-busting hash), or None when it was not uploaded."""
        row = await self.session.scalar(select(GameAsset).where(GameAsset.kind == kind, GameAsset.key == key))
        return view(row)["url"] if row else None

    async def file(self, kind: str, key: str) -> tuple[GameAsset, bytes]:
        row = await self.session.scalar(select(GameAsset).where(GameAsset.kind == kind, GameAsset.key == key))
        if row is None:
            raise AppError(404, "Asset not found")
        return row, self.files.read(row.storage_key)

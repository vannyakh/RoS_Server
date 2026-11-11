"""Map drafts, publication, and package checks."""

import struct
import zlib
from pathlib import Path

import pytest

from app.core.config import get_settings

PASSWORD = "StrongTestPassword123!"


def _png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes((40, 90, 140)) * 8 for _ in range(8))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


async def _login(client, username: str) -> str:
    created = await client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
    assert created.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _allow(monkeypatch, username: str, storage: Path) -> None:
    monkeypatch.setenv("MAP_PUBLISHERS", username)
    monkeypatch.setenv("MAP_STORAGE_DIR", str(storage))
    get_settings.cache_clear()


def _version_body() -> dict:
    return {
        "version": "1.0.0",
        "size": [256, 100, 256],
        "regions": [{"code": "village", "name": "Village", "minimum": [0, 0, 0], "maximum": [80, 20, 80]}],
        "objects": [
            {
                "object_code": "building_warehouse_001",
                "definition_code": "building_warehouse",
                "category": "building",
                "position": [20, 0, 30],
                "collision": True,
                "navigation_obstacle": True,
                "interactive": False,
            }
        ],
        "spawn_points": [
            {"spawn_code": "spawn_001", "position": [10, 0, 10], "spawn_group": "alpha"},
            {"spawn_code": "spawn_002", "position": [12, 0, 10], "spawn_group": "alpha"},
            {"spawn_code": "spawn_003", "position": [40, 0, 40], "spawn_group": "beta"},
            {"spawn_code": "spawn_004", "position": [42, 0, 40], "spawn_group": "beta"},
        ],
        "points_of_interest": [{"poi_code": "bridge", "name": "Bridge", "position": [50, 0, 50], "icon": "bridge"}],
    }


async def _draft(client, headers: dict[str, str]) -> tuple[str, str]:
    created = await client.post(
        "/api/v1/admin/maps",
        headers=headers,
        json={"code": "island_alpha", "name": "Island Alpha", "description": "Original test map", "width": 256, "height": 256},
    )
    assert created.status_code == 201
    map_id = created.json()["id"]
    version = await client.post(f"/api/v1/admin/maps/{map_id}/versions", headers=headers, json=_version_body())
    assert version.status_code == 201
    return map_id, version.json()["id"]


async def _upload(client, headers, map_id: str, version_id: str, path: str = "minimap/preview.png"):
    return await client.post(
        f"/api/v1/admin/maps/{map_id}/assets",
        headers=headers,
        data={"version_id": version_id, "asset_type": "minimap", "relative_path": path},
        files={"upload": ("preview.png", _png(), "image/png")},
    )


@pytest.fixture
def map_dir(tmp_path, monkeypatch):
    _allow(monkeypatch, "map_admin", tmp_path)
    return tmp_path


async def test_publish_catalog_and_verified_manifest(client, map_dir):
    token = await _login(client, "map_admin")
    headers = _headers(token)
    map_id, version_id = await _draft(client, headers)
    uploaded = await _upload(client, headers, map_id, version_id)
    assert uploaded.status_code == 201
    digest = uploaded.json()["sha256"]
    assert len(digest) == 64
    assert int(digest, 16) >= 0

    hidden = await client.get("/api/v1/maps")
    assert hidden.status_code == 200
    assert hidden.json()["total"] == 0

    published = await client.post(
        f"/api/v1/admin/maps/{map_id}/publish",
        headers=headers,
        json={"version_id": version_id},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    manifest_hash = published.json()["manifest_hash"]

    catalog = await client.get("/api/v1/maps")
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 1
    assert catalog.json()["items"][0]["slug"] == "island_alpha"
    assert catalog.json()["items"][0]["manifest_hash"] == manifest_hash

    detail = await client.get(f"/api/v1/maps/{map_id}")
    assert detail.status_code == 200
    assert detail.json()["coordinate_system"] == "local_xyz_y_up_meters"
    assert detail.json()["current_version"] == "1.0.0"

    manifest = await client.get(f"/api/v1/maps/{map_id}/manifest")
    assert manifest.status_code == 200
    body = manifest.json()
    assert body["manifest_hash"] == manifest_hash
    assert body["files"][0]["sha256"] == digest
    asset = await client.get(f"/api/v1/maps/{map_id}/assets/{body['files'][0]['asset_id']}")
    assert asset.status_code == 200
    assert asset.content.startswith(b"\x89PNG")

    again = await client.post(f"/api/v1/admin/maps/{map_id}/publish", headers=headers, json={"version_id": version_id})
    assert again.status_code == 409
    changed = await _upload(client, headers, map_id, version_id, "minimap/other.png")
    assert changed.status_code == 409


async def test_duplicate_version_invalid_path_and_bounds(client, map_dir):
    token = await _login(client, "map_admin")
    headers = _headers(token)
    map_id, _version_id = await _draft(client, headers)
    duplicate = await client.post(f"/api/v1/admin/maps/{map_id}/versions", headers=headers, json=_version_body())
    assert duplicate.status_code == 409

    outside = _version_body()
    outside["version"] = "1.0.1"
    outside["spawn_points"] = [{"spawn_code": "spawn_far", "position": [999, 0, 10]}]
    rejected = await client.post(f"/api/v1/admin/maps/{map_id}/versions", headers=headers, json=outside)
    assert rejected.status_code == 422

    version = await client.post(
        f"/api/v1/admin/maps/{map_id}/versions",
        headers=headers,
        json={**_version_body(), "version": "1.0.2"},
    )
    assert version.status_code == 201
    traversal = await _upload(client, headers, map_id, version.json()["id"], "../secret.png")
    assert traversal.status_code == 422


async def test_missing_file_and_hash_mismatch_block_publish(client, map_dir):
    token = await _login(client, "map_admin")
    headers = _headers(token)
    map_id, version_id = await _draft(client, headers)
    uploaded = await _upload(client, headers, map_id, version_id)
    assert uploaded.status_code == 201
    stored = map_dir / "maps" / map_id / "1.0.0" / "minimap" / "preview.png"
    stored.write_bytes(b"tampered")
    mismatch = await client.post(f"/api/v1/admin/maps/{map_id}/publish", headers=headers, json={"version_id": version_id})
    assert mismatch.status_code == 422
    stored.unlink()
    missing = await client.post(f"/api/v1/admin/maps/{map_id}/publish", headers=headers, json={"version_id": version_id})
    assert missing.status_code == 422


async def test_player_cannot_publish(client, map_dir):
    admin = await _login(client, "map_admin")
    player = await _login(client, "map_player")
    map_id, version_id = await _draft(client, _headers(admin))
    assert (await _upload(client, _headers(admin), map_id, version_id)).status_code == 201
    denied = await client.post(
        f"/api/v1/admin/maps/{map_id}/publish",
        headers=_headers(player),
        json={"version_id": version_id},
    )
    assert denied.status_code == 403


async def test_pin_published_version_on_a_match(client, map_dir):
    token = await _login(client, "map_admin")
    headers = _headers(token)
    map_id, version_id = await _draft(client, headers)
    assert (await _upload(client, headers, map_id, version_id)).status_code == 201
    published = await client.post(f"/api/v1/admin/maps/{map_id}/publish", headers=headers, json={"version_id": version_id})
    assert published.status_code == 200
    match = await client.post("/api/v1/match-records", headers=headers, json={"match_code": "map-match-1", "max_players": 8})
    assert match.status_code == 201
    pinned = await client.post(
        f"/api/v1/admin/maps/{map_id}/pin",
        headers=headers,
        json={"version_id": version_id, "match_id": match.json()["id"]},
    )
    assert pinned.status_code == 204
    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.match import Match

    async with SessionLocal() as session:
        row = await session.scalar(select(Match).where(Match.id == match.json()["id"]))
        assert row is not None
        assert row.map_id == map_id
        assert row.map_version_id == version_id
        assert row.manifest_hash == published.json()["manifest_hash"]

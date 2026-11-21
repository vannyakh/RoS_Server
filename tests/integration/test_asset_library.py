"""Asset library: operators upload images by kind and key; anyone fetches them by URL."""

import pytest

PASSWORD = "StrongTestPassword123!"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
OTHER_PNG = b"\x89PNG\r\n\x1a\n" + b"\x01" * 32


@pytest.fixture
def asset_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "game_asset_dir", str(tmp_path))
    return tmp_path


async def _operator(client, username: str, roles: list[str]) -> dict[str, str]:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


def _form(kind: str, key: str, data: bytes, source: str = "test fixture"):
    return {"data": {"kind": kind, "key": key, "name": f"Prop {key}", "source": source}, "files": {"upload": ("x.png", data)}}


async def test_upload_serve_replace_and_delete(client, asset_dir):
    headers = await _operator(client, "asset_admin", ["support"])

    created = await client.post("/api/v1/admin/assets", headers=headers, **_form("prop", "70001", PNG))
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["kind"], body["key"], body["content_type"], body["source"]) == ("prop", "70001", "image/png", "test fixture")
    assert body["url"].startswith("/api/v1/assets/prop/70001?v=")

    served = await client.get("/api/v1/assets/prop/70001")
    assert served.status_code == 200
    assert served.content == PNG
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"

    replaced = await client.post("/api/v1/admin/assets", headers=headers, **_form("prop", "70001", OTHER_PNG))
    assert replaced.json()["id"] == body["id"]
    assert replaced.json()["url"] != body["url"]
    assert (await client.get("/api/v1/assets/prop/70001")).content == OTHER_PNG

    listed = await client.get("/api/v1/admin/assets?kind=prop", headers=headers)
    assert listed.json()["total"] == 1

    deleted = await client.delete(f"/api/v1/admin/assets/{body['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/assets/prop/70001")).status_code == 404
    assert not any(asset_dir.rglob("*.png"))

    audit = await client.get("/api/v1/admin/audit", headers=headers)
    actions = {row["action"] for row in audit.json()}
    assert {"asset.upload", "asset.replace", "asset.delete"} <= actions


async def test_rejects_non_images_svg_bad_keys_and_missing_permission(client, asset_dir):
    headers = await _operator(client, "asset_support", ["support"])
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("prop", "1", svg))).status_code == 415
    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("prop", "../x", PNG))).status_code == 422
    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("weapon", "1", PNG))).status_code == 422
    too_big = PNG + b"\x00" * (2 * 1024 * 1024)
    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("prop", "2", too_big))).status_code == 413

    limited = await _operator(client, "asset_viewer", ["game_admin"])
    denied = await client.post("/api/v1/admin/assets", headers=limited, **_form("prop", "3", PNG))
    assert denied.status_code == 403
    assert (await client.post("/api/v1/admin/assets", **_form("prop", "3", PNG))).status_code == 401


def _glb() -> bytes:
    """Smallest valid binary glTF 2.0: header plus one JSON chunk."""
    payload = b'{"asset":{"version":"2.0"}}'
    payload += b" " * (-len(payload) % 4)
    chunk = len(payload).to_bytes(4, "little") + b"JSON" + payload
    total = 12 + len(chunk)
    return b"glTF" + (2).to_bytes(4, "little") + total.to_bytes(4, "little") + chunk


async def test_models_take_glb_only_and_glb_only_goes_in_models(client, asset_dir):
    headers = await _operator(client, "model_admin", ["support"])
    model = _glb()
    created = await client.post("/api/v1/admin/assets", headers=headers, **_form("model", "skin-field_jacket", model))
    assert created.status_code == 201, created.text
    assert created.json()["content_type"] == "model/gltf-binary"
    served = await client.get("/api/v1/assets/model/skin-field_jacket")
    assert served.status_code == 200
    assert served.content == model
    assert served.headers["content-type"] == "model/gltf-binary"

    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("item", "x", model))).status_code == 415
    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("model", "y", PNG))).status_code == 415
    truncated = model[:-4]
    assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("model", "z", truncated))).status_code == 422


async def test_model_status_lists_targets_and_unlinked_uploads(client, asset_dir):
    from app.infrastructure.database import SessionLocal
    from app.models.game_data import ItemDefinition

    headers = await _operator(client, "status_admin", ["support"])
    async with SessionLocal() as session:
        item = ItemDefinition(code="status_item", name="Status Item", category="weapon", max_stack=1)
        session.add(item)
        await session.commit()
        item_id = item.id

    model = _glb()
    for key in (f"item-{item_id}", "skin-field_jacket", "prop-1", "stray-model"):
        assert (await client.post("/api/v1/admin/assets", headers=headers, **_form("model", key, model))).status_code == 201

    status = await client.get("/api/v1/admin/assets/models/status", headers=headers)
    assert status.status_code == 200, status.text
    body = status.json()
    by_key = {row["key"]: row for row in body["items"]}
    assert by_key[f"item-{item_id}"]["status"] == "ready"
    assert by_key[f"item-{item_id}"]["label"] == "Status Item"
    assert by_key["skin-field_jacket"]["status"] == "ready"
    assert by_key["skin-recruit"]["status"] == "missing"
    assert by_key["stray-model"]["status"] == "unlinked"
    assert by_key["stray-model"]["type"] == "other"
    assert by_key["prop-1"]["status"] == "ready"
    assert by_key["prop-1"]["type"] == "prop"
    assert by_key["prop-1"]["label"] == "Lv 1 helmet"
    assert by_key["lobby-1"]["type"] == "lobby" and by_key["lobby-1"]["detail"] == "character"
    lobby_details = {row["detail"] for row in body["items"] if row["type"] == "lobby"}
    assert lobby_details == {"firearms", "clothes", "character", "vehicles", "companions"}
    summary = body["summary"]
    assert summary["ready"] == 3 and summary["unlinked"] == 1
    assert summary["targets"] == summary["ready"] + summary["missing"]
    assert summary["by_type"]["skin"]["total"] == 9
    assert summary["by_type"]["prop"] == {"total": 411, "ready": 1}
    assert summary["by_type"]["lobby"]["total"] == 5031
    assert (await client.get("/api/v1/admin/assets/models/status")).status_code == 401

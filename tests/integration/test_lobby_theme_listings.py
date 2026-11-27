"""Lobby theme store listings: operators price themes and take them off sale; the gateway reads
the overrides from /api/v1/gateway/store/listings."""

import pytest

PASSWORD = "StrongTestPassword123!"
KEY = "test-gateway-key"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SCHOOLGIRL = 270002          # mall good 10002, 280 diamonds in the client table
FIORD = 270000               # mall good 10000, 0 coins (GP)
NO_GOOD = 270001             # a theme the client store does not sell


@pytest.fixture
def gateway_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gateway_api_key", KEY)
    return {"X-Gateway-Key": KEY}


async def _operator(client, username: str, roles: list[str], grants: tuple[str, ...] = ()) -> dict[str, str]:
    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.operator import Permission, Role, RolePermission
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        if grants:
            await OperatorService(session).ensure_catalog()
            role = Role(code=f"r_{username}", name=username, description="")
            session.add(role)
            await session.flush()
            for code in grants:
                permission = await session.scalar(select(Permission).where(Permission.code == code))
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            await session.commit()
            roles = [*roles, role.code]
        await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)
    logged_in = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200, logged_in.text
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


def _by_id(items):
    return {row["id"]: row for row in items}


async def test_list_shows_every_theme_with_game_defaults(client):
    headers = await _operator(client, "theme_reader", ["support"])

    response = await client.get("/api/v1/admin/original/lobby-themes", headers=headers)

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 21
    assert [row["id"] for row in items] == sorted(row["id"] for row in items)
    assert items[0]["id"] == FIORD
    rows = _by_id(items)
    school = rows[SCHOOLGIRL]
    assert school["name"] == "Schoolgirl"
    assert (school["goods_id"], school["default_on_sale"], school["default_currency"], school["default_price"]) == (10002, True, "diamond", 280)
    assert (school["on_sale"], school["currency"], school["price"], school["overridden"]) == (True, "diamond", 280, False)
    assert (school["background_url"], school["updated_at"], school["updated_by"]) == ("", None, None)
    assert {"description", "quality", "icon_path"} <= set(school)
    assert (rows[FIORD]["default_currency"], rows[FIORD]["default_price"]) == ("coin", 0)
    none = rows[NO_GOOD]
    assert (none["goods_id"], none["default_on_sale"], none["default_currency"], none["default_price"]) == (None, False, None, None)
    assert (none["on_sale"], none["currency"], none["price"]) == (False, "diamond", 0)


async def test_override_then_clear_with_audit_and_gateway_feed(client, gateway_key):
    headers = await _operator(client, "theme_admin", ["support"])

    changed = await client.put(
        f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing",
        headers=headers,
        json={"on_sale": True, "currency": "coin", "price": 1500, "reason": "Spring event"},
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["on_sale"], body["currency"], body["price"], body["overridden"]) == (True, "coin", 1500, True)
    assert (body["default_currency"], body["default_price"]) == ("diamond", 280)
    assert body["updated_by"] == "theme_admin" and body["updated_at"]

    off = await client.put(
        f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing",
        headers=headers,
        json={"on_sale": False, "currency": "diamond", "price": 280, "reason": "Retired"},
    )
    assert off.json()["on_sale"] is False

    feed = await client.get("/api/v1/gateway/store/listings", headers=gateway_key)
    assert feed.status_code == 200
    assert feed.json() == {"listings": [{"item_id": SCHOOLGIRL, "goods_id": 10002, "on_sale": False, "currency": "diamond", "price": 280}]}

    listed = _by_id((await client.get("/api/v1/admin/original/lobby-themes", headers=headers)).json()["items"])
    assert listed[SCHOOLGIRL]["overridden"] is True and listed[SCHOOLGIRL]["on_sale"] is False

    cleared = await client.delete(f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing?reason=back+to+default", headers=headers)
    assert cleared.status_code == 200, cleared.text
    assert (cleared.json()["overridden"], cleared.json()["on_sale"], cleared.json()["price"], cleared.json()["updated_by"]) == (False, True, 280, None)
    assert (await client.get("/api/v1/gateway/store/listings", headers=gateway_key)).json() == {"listings": []}

    audit = [row for row in (await client.get("/api/v1/admin/audit", headers=headers)).json() if row["action"] == "store.listing"]
    assert len(audit) == 3
    details = " | ".join(row["detail"] for row in audit)
    assert "Schoolgirl: coin 1500" in details and "Schoolgirl: off sale" in details and "Schoolgirl: game default" in details
    assert {row["reason"] for row in audit} == {"Spring event", "Retired", "back to default"}


async def test_background_url_comes_from_the_asset_library(client):
    headers = await _operator(client, "theme_bg", ["support"])
    uploaded = await client.post(
        "/api/v1/admin/assets",
        headers=headers,
        data={"kind": "background", "key": str(SCHOOLGIRL), "name": "Schoolgirl bg", "source": "test fixture"},
        files={"upload": ("bg.png", PNG)},
    )
    assert uploaded.status_code == 201, uploaded.text

    rows = _by_id((await client.get("/api/v1/admin/original/lobby-themes", headers=headers)).json()["items"])
    assert rows[SCHOOLGIRL]["background_url"].startswith(f"/api/v1/assets/background/{SCHOOLGIRL}?v=")
    assert rows[FIORD]["background_url"] == ""
    put = await client.put(
        f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing",
        headers=headers,
        json={"on_sale": True, "currency": "diamond", "price": 100, "reason": "sale"},
    )
    assert put.json()["background_url"] == rows[SCHOOLGIRL]["background_url"]


async def test_validation_unknown_theme_and_no_store_good(client):
    headers = await _operator(client, "theme_validate", ["support"])
    url = f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing"
    good = {"on_sale": True, "currency": "diamond", "price": 10, "reason": "ok"}

    assert (await client.put("/api/v1/admin/original/lobby-themes/999999/listing", headers=headers, json=good)).status_code == 404
    assert (await client.put("/api/v1/admin/original/lobby-themes/120901/listing", headers=headers, json=good)).status_code == 404
    assert (await client.delete("/api/v1/admin/original/lobby-themes/999999/listing?reason=x", headers=headers)).status_code == 404
    no_good = await client.put(f"/api/v1/admin/original/lobby-themes/{NO_GOOD}/listing", headers=headers, json=good)
    assert no_good.status_code == 422
    off = await client.put(f"/api/v1/admin/original/lobby-themes/{NO_GOOD}/listing", headers=headers, json={**good, "on_sale": False})
    assert off.status_code == 200 and off.json()["overridden"] is True
    for bad in ({"currency": "gold"}, {"price": -1}, {"price": 1_000_001}, {"reason": ""}, {"reason": "x" * 201}):
        assert (await client.put(url, headers=headers, json={**good, **bad})).status_code == 422, bad
    assert (await client.delete(url, headers=headers)).status_code == 422          # reason required


async def test_permissions(client, gateway_key):
    observer = await _operator(client, "theme_observer", ["observer"])
    reader = await _operator(client, "theme_store_reader", [], grants=("store.read",))
    body = {"on_sale": True, "currency": "diamond", "price": 10, "reason": "x"}
    url = f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing"

    assert (await client.get("/api/v1/admin/original/lobby-themes", headers=observer)).status_code == 403
    assert (await client.get("/api/v1/admin/original/lobby-themes", headers=reader)).status_code == 200
    assert (await client.put(url, headers=reader, json=body)).status_code == 403
    assert (await client.delete(url + "?reason=x", headers=reader)).status_code == 403
    assert (await client.get("/api/v1/gateway/store/listings")).status_code == 401


async def test_store_manage_is_in_the_catalog_and_the_support_role(client):
    from sqlalchemy import select

    from app.infrastructure.database import SessionLocal
    from app.models.operator import Permission, Role, RolePermission
    from app.services.operator_service import CATALOG, OperatorService

    assert "store.manage" in dict(CATALOG)
    async with SessionLocal() as session:
        await OperatorService(session).ensure_catalog()
        held = await session.scalar(
            select(RolePermission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Role.code == "support", Permission.code == "store.manage")
        )
    assert held is not None


async def test_list_filters_by_column(client):
    headers = await _operator(client, "theme_filter", ["support"])
    await client.put(
        f"/api/v1/admin/original/lobby-themes/{SCHOOLGIRL}/listing",
        headers=headers,
        json={"on_sale": True, "currency": "coin", "price": 99, "reason": "event"},
    )

    async def ids(query: str) -> list[int]:
        response = await client.get(f"/api/v1/admin/original/lobby-themes?{query}", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == len(body["items"])
        return [row["id"] for row in body["items"]]

    assert await ids("") == sorted(await ids(""))
    assert len(await ids("")) == 21
    assert await ids("q=school") == [SCHOOLGIRL]
    assert await ids(f"q={SCHOOLGIRL}") == [SCHOOLGIRL]
    assert await ids("q=10003") == [270003]                       # goods id
    no_good = [NO_GOOD, 279004, 279016]                           # no client mall good
    in_store = await ids("in_store=true")
    assert len(in_store) == 18 and not set(no_good) & set(in_store)
    assert await ids("in_store=false") == no_good
    assert await ids("on_sale=true") == in_store
    assert await ids("overridden=true") == [SCHOOLGIRL]
    assert await ids("currency=coin&on_sale=true") == [270000, SCHOOLGIRL]
    assert await ids("has_background=true") == []
    quality = (await client.get("/api/v1/admin/original/lobby-themes", headers=headers)).json()["items"][2]["quality"]
    assert SCHOOLGIRL in await ids(f"quality={quality}")
    assert (await client.get("/api/v1/admin/original/lobby-themes?currency=gold", headers=headers)).status_code == 422

"""Operators are separate from player accounts, and permissions follow the caller's roles."""

PASSWORD = "StrongTestPassword123!"


async def _support(client):
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator("support_admin", PASSWORD, ["support"], audit=False)
    logged_in = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "support_admin", "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_player_token_cannot_open_the_operator_panel(client):
    created = await client.post(
        "/api/v1/auth/register",
        json={"username": "plain_player", "password": PASSWORD},
    )
    assert created.status_code == 201
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"username": "plain_player", "password": PASSWORD},
    )
    denied = await client.get("/api/v1/admin/players", headers=_headers(logged_in.json()["access_token"]))
    assert denied.status_code == 401
    staff = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "plain_player", "password": PASSWORD},
    )
    assert staff.status_code == 401


async def test_support_admin_creates_a_role_and_a_limited_operator(client):
    await client.post("/api/v1/auth/register", json={"username": "listed_player", "password": PASSWORD})
    token = await _support(client)
    players = await client.get("/api/v1/admin/players", headers=_headers(token))
    assert players.status_code == 200
    assert any(item["username"] == "listed_player" for item in players.json()["items"])

    created = await client.post(
        "/api/v1/admin/roles",
        headers=_headers(token),
        json={"code": "reader", "name": "Reader", "description": "Player list only"},
    )
    assert created.status_code == 201
    role_id = created.json()["id"]
    granted = await client.put(
        f"/api/v1/admin/roles/{role_id}/permissions",
        headers=_headers(token),
        json={"permissions": ["players.read"]},
    )
    assert granted.status_code == 200
    refused = await client.put(
        f"/api/v1/admin/roles/{role_id}/permissions",
        headers=_headers(token),
        json={"permissions": ["not.a.permission"]},
    )
    assert refused.status_code == 403

    operator = await client.post(
        "/api/v1/admin/operators",
        headers=_headers(token),
        json={"username": "reader_one", "password": PASSWORD, "roles": ["reader"]},
    )
    assert operator.status_code == 201
    reader_login = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "reader_one", "password": PASSWORD},
    )
    reader = reader_login.json()["access_token"]
    assert (await client.get("/api/v1/admin/players", headers=_headers(reader))).status_code == 200
    assert (await client.post("/api/v1/admin/roles", headers=_headers(reader), json={"code": "extra", "name": "Extra"})).status_code == 403

    account_id = next(item["id"] for item in players.json()["items"] if item["username"] == "listed_player")
    suspended = await client.patch(
        f"/api/v1/admin/players/{account_id}",
        headers=_headers(token),
        json={"status": "suspended"},
    )
    assert suspended.status_code == 200
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"username": "listed_player", "password": PASSWORD},
    )
    assert blocked.status_code == 401

    audit = await client.get("/api/v1/admin/audit", headers=_headers(token))
    assert audit.status_code == 200
    assert any(row["action"] == "role.create" for row in audit.json())
    logs = await client.get("/api/v1/admin/logs", headers=_headers(token))
    assert logs.status_code == 200
    assert isinstance(logs.json()["lines"], list)

"""Durable lobby routes backed by the existing lobby service."""

PASSWORD = "StrongTestPassword123!"


async def _token(client, username: str) -> str:
    created = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert created.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def test_items_and_lobby_membership(client):
    catalog = await client.get("/api/v1/items")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert isinstance(body["items"], list)

    token = await _token(client, "lobby_host")
    headers = {"Authorization": f"Bearer {token}"}
    denied = await client.post("/api/v1/lobby", json={"code": "ROOM1", "max_players": 4})
    assert denied.status_code == 401

    opened = await client.post("/api/v1/lobby", json={"code": "ROOM1", "max_players": 4}, headers=headers)
    assert opened.status_code == 201
    lobby_id = opened.json()["id"]
    assert opened.json()["code"] == "ROOM1"
    assert opened.json()["current_players"] == 0

    duplicate = await client.post("/api/v1/lobby", json={"code": "ROOM1", "max_players": 4}, headers=headers)
    assert duplicate.status_code == 409

    joined = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=headers)
    assert joined.status_code == 201
    assert joined.json()["player_id"]

    team = await client.post(
        f"/api/v1/lobby/{lobby_id}/teams",
        json={"code": "A", "name": "Alpha"},
        headers=headers,
    )
    assert team.status_code == 201
    seated = await client.post(f"/api/v1/lobby/teams/{team.json()['id']}/members", headers=headers)
    assert seated.status_code == 201
    assert seated.json()["team_id"] == team.json()["id"]

    again = await client.post(f"/api/v1/lobby/teams/{team.json()['id']}/members", headers=headers)
    assert again.status_code == 409

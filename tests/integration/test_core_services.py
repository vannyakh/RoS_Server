"""Durable inventory, team leave, and stored match lifecycle."""

from app.database.seeds.seed_items import seed_items
from app.infrastructure.database import SessionLocal

PASSWORD = "StrongTestPassword123!"


async def _token(client, username: str) -> str:
    created = await client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
    assert created.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert login.status_code == 200
    return login.json()["access_token"]


async def test_inventory_stack_and_currency(client):
    async with SessionLocal() as session:
        await seed_items(session)
        await session.commit()
    token = await _token(client, "inventory_player")
    headers = {"Authorization": f"Bearer {token}"}

    empty = await client.get("/api/v1/inventory", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["currencies"] == []

    added = await client.post(
        "/api/v1/inventory/items",
        json={"item_code": "TEST_ITEM", "quantity": 2},
        headers=headers,
    )
    assert added.status_code == 200
    assert added.json()["quantity"] == 2

    overflow = await client.post(
        "/api/v1/inventory/items",
        json={"item_code": "TEST_ITEM", "quantity": 100},
        headers=headers,
    )
    assert overflow.status_code == 409

    removed = await client.post(
        "/api/v1/inventory/items/remove",
        json={"item_code": "TEST_ITEM", "quantity": 1},
        headers=headers,
    )
    assert removed.status_code == 200
    assert removed.json()["quantity"] == 1

    short = await client.post(
        "/api/v1/inventory/items/remove",
        json={"item_code": "TEST_ITEM", "quantity": 5},
        headers=headers,
    )
    assert short.status_code == 409

    paid = await client.post(
        "/api/v1/inventory/currency",
        json={"currency_code": "TEST", "amount": 10, "reason": "fixture"},
        headers=headers,
    )
    assert paid.status_code == 200
    assert paid.json()["balance"] == 10
    overdrawn = await client.post(
        "/api/v1/inventory/currency",
        json={"currency_code": "TEST", "amount": -11, "reason": "fixture"},
        headers=headers,
    )
    assert overdrawn.status_code == 409


async def test_team_leave_keeps_lobby_membership(client):
    token = await _token(client, "team_player")
    headers = {"Authorization": f"Bearer {token}"}
    opened = await client.post("/api/v1/lobby", json={"code": "TEAMROOM", "max_players": 4}, headers=headers)
    assert opened.status_code == 201
    lobby_id = opened.json()["id"]
    await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=headers)
    team = await client.post(
        f"/api/v1/lobby/{lobby_id}/teams",
        json={"code": "B", "name": "Bravo"},
        headers=headers,
    )
    team_id = team.json()["id"]
    seated = await client.post(f"/api/v1/lobby/teams/{team_id}/members", headers=headers)
    assert seated.status_code == 201

    left = await client.delete(f"/api/v1/lobby/teams/{team_id}/members", headers=headers)
    assert left.status_code == 204
    missing = await client.delete(f"/api/v1/lobby/teams/{team_id}/members", headers=headers)
    assert missing.status_code == 404

    ready = await client.post(f"/api/v1/lobby/{lobby_id}/ready", json={"ready": True}, headers=headers)
    assert ready.status_code == 200
    assert ready.json()["ready"] is True


async def test_match_record_cancel_and_finalize(client):
    token = await _token(client, "match_player")
    headers = {"Authorization": f"Bearer {token}"}
    other = await _token(client, "match_other")
    other_headers = {"Authorization": f"Bearer {other}"}

    created = await client.post(
        "/api/v1/match-records",
        json={"match_code": "LIFE-1", "max_players": 4},
        headers=headers,
    )
    assert created.status_code == 201
    match_id = created.json()["id"]
    assert created.json()["status"] == "scheduled"

    duplicate = await client.post(
        "/api/v1/match-records",
        json={"match_code": "LIFE-1", "max_players": 4},
        headers=headers,
    )
    assert duplicate.status_code == 409

    outsider = await client.post(
        f"/api/v1/match-records/{match_id}/transition",
        json={"status": "cancelled"},
        headers=other_headers,
    )
    assert outsider.status_code == 403

    joined = await client.post(f"/api/v1/match-records/{match_id}/participants", headers=headers)
    assert joined.status_code == 204
    cancelled = await client.post(
        f"/api/v1/match-records/{match_id}/transition",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    again = await client.post(
        f"/api/v1/match-records/{match_id}/transition",
        json={"status": "lobby"},
        headers=headers,
    )
    assert again.status_code == 409

    second = await client.post(
        "/api/v1/match-records",
        json={"match_code": "LIFE-2", "max_players": 4},
        headers=headers,
    )
    second_id = second.json()["id"]
    await client.post(f"/api/v1/match-records/{second_id}/participants", headers=headers)
    await client.post(f"/api/v1/match-records/{second_id}/transition", json={"status": "lobby"}, headers=headers)
    running = await client.post(
        f"/api/v1/match-records/{second_id}/transition",
        json={"status": "running"},
        headers=headers,
    )
    assert running.status_code == 200
    profile = await client.get("/api/v1/players/me", headers=headers)
    finished = await client.post(
        f"/api/v1/match-records/{second_id}/results",
        json={"results": [{"player_id": profile.json()["player_id"], "placement": 1, "kills": 1, "score": 5}]},
        headers=headers,
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    live = await client.get("/api/v1/matches")
    assert live.status_code == 200

"""Profile updates, durable lobby rules, and stored-match limits."""

import asyncio

PASSWORD = "StrongTestPassword123!"


async def _token(client, username: str) -> str:
    created = await client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
    assert created.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _player_id(client, token: str) -> str:
    profile = await client.get("/api/v1/players/me", headers=_headers(token))
    assert profile.status_code == 200
    return profile.json()["player_id"]


async def test_profile_update_changes_only_nickname_and_avatar(client):
    token = await _token(client, "profile_host")
    headers = _headers(token)
    before = await client.get("/api/v1/players/me", headers=headers)
    assert before.json()["username"] == "profile_host"
    assert before.json()["level"] == 1

    renamed = await client.patch(
        "/api/v1/players/me",
        json={"nickname": "Renamed_Host", "avatar_id": "avatar-1", "level": 9},
        headers=headers,
    )
    assert renamed.status_code == 200
    body = renamed.json()
    assert body["username"] == "profile_host"
    assert body["nickname"] == "renamed_host"
    assert body["level"] == 1
    assert body["id"] == before.json()["id"]

    other = await _token(client, "profile_guest")
    conflict = await client.patch(
        "/api/v1/players/me",
        json={"nickname": "renamed_host"},
        headers=_headers(other),
    )
    assert conflict.status_code == 409
    kept = await client.get("/api/v1/players/me", headers=_headers(other))
    assert kept.json()["nickname"] == "profile_guest"

    invalid = await client.patch("/api/v1/players/me", json={"nickname": "no"}, headers=headers)
    assert invalid.status_code == 422


async def test_lobby_membership_ready_leave_and_reads(client):
    host = await _token(client, "room_host")
    guest = await _token(client, "room_guest")
    host_headers = _headers(host)
    guest_headers = _headers(guest)

    opened = await client.post("/api/v1/lobby", json={"code": "ROOM-A", "max_players": 2}, headers=host_headers)
    assert opened.status_code == 201
    lobby_id = opened.json()["id"]

    missing = await client.get("/api/v1/lobby/not-a-lobby", headers=host_headers)
    assert missing.status_code == 404

    hidden = await client.get(f"/api/v1/lobby/{lobby_id}", headers=host_headers)
    assert hidden.status_code == 403

    joined = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=host_headers)
    assert joined.status_code == 201
    duplicate = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=host_headers)
    assert duplicate.status_code == 409

    guest_join = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=guest_headers)
    assert guest_join.status_code == 201
    detail = await client.get(f"/api/v1/lobby/{lobby_id}", headers=guest_headers)
    assert detail.status_code == 200
    assert detail.json()["current_players"] == 2
    members = await client.get(f"/api/v1/lobby/{lobby_id}/members", headers=guest_headers)
    assert members.status_code == 200
    assert len(members.json()) == 2

    ready = await client.post(f"/api/v1/lobby/{lobby_id}/ready", json={"ready": True}, headers=guest_headers)
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    cancelled = await client.post(f"/api/v1/lobby/{lobby_id}/ready", json={"ready": False}, headers=guest_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["ready"] is False

    outsider = await _token(client, "room_outsider")
    outsider_headers = _headers(outsider)
    denied = await client.post(f"/api/v1/lobby/{lobby_id}/ready", json={"ready": True}, headers=outsider_headers)
    assert denied.status_code == 409
    denied_read = await client.get(f"/api/v1/lobby/{lobby_id}/members", headers=outsider_headers)
    assert denied_read.status_code == 403

    full_room = await client.post("/api/v1/lobby", json={"code": "ROOM-FULL", "max_players": 1}, headers=host_headers)
    full_id = full_room.json()["id"]
    assert (await client.post(f"/api/v1/lobby/{full_id}/members", headers=host_headers)).status_code == 201
    rejected = await client.post(f"/api/v1/lobby/{full_id}/members", headers=guest_headers)
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "Lobby is full"

    left = await client.delete(f"/api/v1/lobby/{lobby_id}/members", headers=guest_headers)
    assert left.status_code == 204
    still_open = await client.get(f"/api/v1/lobby/{lobby_id}", headers=host_headers)
    assert still_open.status_code == 200
    assert still_open.json()["status"] == "open"

    host_left = await client.delete(f"/api/v1/lobby/{lobby_id}/members", headers=host_headers)
    assert host_left.status_code == 204
    rejoin = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=host_headers)
    assert rejoin.status_code == 409
    assert rejoin.json()["detail"] == "Lobby is not open"


async def test_concurrent_join_keeps_the_lobby_at_capacity(client):
    from app.core.exceptions import AppError
    from app.infrastructure.database import SessionLocal
    from app.services.lobby_service import LobbyService

    first = await _token(client, "race_one")
    second = await _token(client, "race_two")
    opened = await client.post(
        "/api/v1/lobby",
        json={"code": "ROOM-RACE", "max_players": 1},
        headers=_headers(first),
    )
    assert opened.status_code == 201
    lobby_id = opened.json()["id"]
    first_id = await _player_id(client, first)
    second_id = await _player_id(client, second)

    async def attempt(player_id: str) -> str:
        async with SessionLocal() as session:
            try:
                await LobbyService(session).join(lobby_id, player_id)
            except AppError as exc:
                return exc.detail
            return "ok"

    results = await asyncio.gather(attempt(first_id), attempt(second_id))
    assert results.count("ok") == 1
    assert "Lobby is full" in results


async def test_stored_match_blocks_a_second_active_match_and_does_not_pay_rewards(client):
    token = await _token(client, "reward_player")
    headers = _headers(token)
    player_id = await _player_id(client, token)

    first = await client.post(
        "/api/v1/match-records",
        json={"match_code": "ACTIVE-1", "max_players": 2},
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert (await client.post(f"/api/v1/match-records/{first_id}/participants", headers=headers)).status_code == 204

    second = await client.post(
        "/api/v1/match-records",
        json={"match_code": "ACTIVE-2", "max_players": 2},
        headers=headers,
    )
    second_id = second.json()["id"]
    blocked = await client.post(f"/api/v1/match-records/{second_id}/participants", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Player is already in an active match"

    cancelled = await client.post(
        f"/api/v1/match-records/{first_id}/transition",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert (await client.post(f"/api/v1/match-records/{second_id}/participants", headers=headers)).status_code == 204
    await client.post(f"/api/v1/match-records/{second_id}/transition", json={"status": "lobby"}, headers=headers)
    running = await client.post(
        f"/api/v1/match-records/{second_id}/transition",
        json={"status": "running"},
        headers=headers,
    )
    assert running.status_code == 200
    assert running.json()["current_players"] == 1

    finished = await client.post(
        f"/api/v1/match-records/{second_id}/results",
        json={
            "results": [
                {
                    "player_id": player_id,
                    "placement": 1,
                    "kills": 3,
                    "score": 10,
                    "rewards": {"experience": 500, "currency": 80},
                }
            ]
        },
        headers=headers,
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    repeat = await client.post(
        f"/api/v1/match-records/{second_id}/results",
        json={"results": [{"player_id": player_id, "placement": 1, "kills": 3, "score": 10}]},
        headers=headers,
    )
    assert repeat.status_code == 409

    profile = await client.get("/api/v1/players/me", headers=headers)
    assert profile.json()["level"] == 1
    assert profile.json()["matches_played"] == 0
    assert profile.json()["kills"] == 0
    inventory = await client.get("/api/v1/inventory", headers=headers)
    assert inventory.status_code == 200
    assert inventory.json()["currencies"] == []

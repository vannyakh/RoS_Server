"""Operator live feed: auth, dashboard snapshot, presence and player-change events."""

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

PASSWORD = "StrongTestPassword123!"


def _next_type(websocket, message_type: str) -> dict:
    for _ in range(40):
        message = websocket.receive_json()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"Did not receive {message_type}")


def _operator_token(client: TestClient, username: str, roles: list[str]) -> str:
    async def _create() -> None:
        from app.infrastructure.database import SessionLocal
        from app.services.operator_service import OperatorService

        async with SessionLocal() as session:
            await OperatorService(session).create_operator(username, PASSWORD, roles, audit=False)

    client.portal.call(_create)
    logged_in = client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def test_admin_socket_streams_dashboard_presence_and_changes():
    from app.main import app
    from app.networking.admin_hub import admin_hub

    admin_hub.reset()
    suffix = uuid.uuid4().hex[:8]
    with TestClient(app) as client:
        token = _operator_token(client, f"live_{suffix}", ["support"])
        player_name = f"live_player_{suffix}"
        created = client.post("/api/v1/auth/register", json={"username": player_name, "password": PASSWORD})
        assert created.status_code == 201
        account_id = created.json()["id"]
        player_token = client.post(
            "/api/v1/auth/login", json={"username": player_name, "password": PASSWORD}
        ).json()["access_token"]

        with client.websocket_connect("/api/v1/admin/ws") as admin:
            admin.send_json({"type": "auth", "payload": {"token": token}})
            welcome = _next_type(admin, "auth.ok")
            assert set(welcome["payload"]["permissions"]) == {"dashboard.read", "players.read", "matches.read"}
            snapshot = _next_type(admin, "dashboard.snapshot")
            assert snapshot["payload"]["registered_players"] >= 1
            assert snapshot["payload"]["online_players"] == 0

            with client.websocket_connect("/api/v1/ws") as game:
                game.send_json({"version": 1, "type": "auth", "sequence": 1, "payload": {"token": player_token}})
                _next_type(game, "auth.ok")
                online = _next_type(admin, "player.presence")
                assert online["payload"] == {"account_id": account_id, "online": True, "online_players": 1, "source": "socket"}
            offline = _next_type(admin, "player.presence")
            assert offline["payload"]["online"] is False

            edited = client.patch(
                f"/api/v1/admin/players/{account_id}/profile",
                headers={"Authorization": f"Bearer {token}"},
                json={"level": 4, "reason": "Live feed check."},
            )
            assert edited.status_code == 200
            changed = _next_type(admin, "player.changed")
            assert changed["payload"]["account_id"] == account_id
            assert changed["payload"]["change"] == "profile"

            admin.send_json({"type": "watch", "payload": {"match_id": None}})
            frame = _next_type(admin, "match.frame")
            assert frame["payload"]["watching"] == "*"
            assert frame["payload"]["found"] is True
            assert isinstance(frame["payload"]["matches"], list)
            admin.send_json({"type": "unwatch"})

            admin.send_json({"type": "ping"})
            assert _next_type(admin, "pong")["payload"]["online_players"] == 0


def test_admin_socket_rejects_player_and_missing_tokens():
    from app.main import app

    suffix = uuid.uuid4().hex[:8]
    with TestClient(app) as client:
        player_name = f"not_staff_{suffix}"
        client.post("/api/v1/auth/register", json={"username": player_name, "password": PASSWORD})
        player_token = client.post(
            "/api/v1/auth/login", json={"username": player_name, "password": PASSWORD}
        ).json()["access_token"]

        for token in (player_token, ""):
            with client.websocket_connect("/api/v1/admin/ws") as admin:
                admin.send_json({"type": "auth", "payload": {"token": token}})
                assert admin.receive_json()["type"] == "error"
                with pytest.raises(WebSocketDisconnect) as closed:
                    admin.receive_json()
                assert closed.value.code == 4003

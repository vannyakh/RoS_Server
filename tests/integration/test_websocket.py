"""Authenticated WebSocket input."""

from fastapi.testclient import TestClient

PASSWORD = "StrongTestPassword123!"


def test_websocket_accepts_input_after_auth():
    from app.main import app

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/auth/register",
            json={"username": "socket_player", "password": PASSWORD},
        )
        assert created.status_code == 201
        token = client.post(
            "/api/v1/auth/login",
            json={"username": "socket_player", "password": PASSWORD},
        ).json()["access_token"]

        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {"version": 1, "type": "auth", "sequence": 1, "payload": {"token": token}}
            )
            welcome = _next_type(websocket, "auth.ok")
            assert welcome["payload"]["player_id"]
            websocket.send_json(
                {
                    "version": 1,
                    "type": "player.input",
                    "sequence": 2,
                    "payload": {"move_x": 0.5, "move_y": 0.0},
                }
            )
            ack = _next_type(websocket, "player.input.ack")
            assert ack["sequence"] == 2
            websocket.send_json({"version": 1, "type": "lobby.join", "sequence": 3, "payload": {}})
            joined = _next_type(websocket, "lobby.join.ack")
            assert joined["payload"]["ok"] is True


def _next_type(websocket, message_type: str) -> dict:
    for _ in range(40):
        message = websocket.receive_json()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"Did not receive {message_type}")

"""WebSocket authentication, two clients, disconnect, and reconnect."""

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

PASSWORD = "StrongTestPassword123!"


def _token(client: TestClient, username: str) -> str:
    created = client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
    assert created.status_code == 201
    logged_in = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _auth(websocket, token: str, sequence: int = 1) -> dict:
    websocket.send_json({"version": 1, "type": "auth", "sequence": sequence, "payload": {"token": token}})
    for _ in range(10):
        message = websocket.receive_json()
        if message["type"] == "auth.ok":
            return message
        if message["type"] == "error":
            return message
    raise AssertionError("no auth result")


def test_single_client_auth_and_invalid_token():
    from app.main import app

    with TestClient(app) as client:
        token = _token(client, "ws_one")
        with client.websocket_connect("/api/v1/ws") as websocket:
            welcome = _auth(websocket, token)
            assert welcome["type"] == "auth.ok"
            assert welcome["payload"]["player_id"]
        with client.websocket_connect("/api/v1/ws") as websocket:
            rejected = _auth(websocket, "not-a-token")
            assert rejected["type"] == "error"
            assert rejected["payload"]["detail"] == "Invalid or expired token"


def test_two_clients_disconnect_and_reconnect():
    from app.main import app

    with TestClient(app) as client:
        alpha = _token(client, "ws_alpha")
        bravo = _token(client, "ws_bravo")
        with client.websocket_connect("/api/v1/ws") as first, client.websocket_connect("/api/v1/ws") as second:
            assert _auth(first, alpha)["type"] == "auth.ok"
            assert _auth(second, bravo)["type"] == "auth.ok"
        with client.websocket_connect("/api/v1/ws") as again:
            welcome = _auth(again, alpha)
            assert welcome["type"] == "auth.ok"


def test_a_second_connection_replaces_the_first():
    from app.main import app

    with TestClient(app) as client:
        token = _token(client, "ws_replace")
        with client.websocket_connect("/api/v1/ws") as first:
            assert _auth(first, token)["type"] == "auth.ok"
            with client.websocket_connect("/api/v1/ws") as second:
                assert _auth(second, token)["type"] == "auth.ok"
                closed = False
                for _ in range(20):
                    try:
                        first.receive_json()
                    except WebSocketDisconnect as exc:
                        assert exc.code == 4000
                        closed = True
                        break
                assert closed


def test_two_clients_send_input_and_a_shot_is_rejected_outside_a_match():
    from app.main import app

    def until(websocket, message_type: str) -> dict:
        for _ in range(30):
            message = websocket.receive_json()
            if message["type"] == message_type:
                return message
        raise AssertionError(message_type)

    with TestClient(app) as client:
        alpha = _token(client, "ws_move_alpha")
        bravo = _token(client, "ws_move_bravo")
        with client.websocket_connect("/api/v1/ws") as first, client.websocket_connect("/api/v1/ws") as second:
            assert _auth(first, alpha)["type"] == "auth.ok"
            assert _auth(second, bravo)["type"] == "auth.ok"
            first.send_json(
                {
                    "version": 1,
                    "type": "player.input",
                    "sequence": 2,
                    "payload": {"move_x": 1, "move_y": 0, "aim_x": 1, "aim_y": 0},
                }
            )
            second.send_json(
                {
                    "version": 1,
                    "type": "player.action",
                    "sequence": 2,
                    "payload": {"action": "shoot"},
                }
            )
            move = until(first, "player.input.ack")
            shot = until(second, "player.action.ack")
            assert isinstance(move["payload"]["tick"], int)
            assert shot["payload"]["ok"] is False
            assert shot["payload"]["detail"] == "Not in a match"


def test_revoked_token_is_rejected_on_websocket():
    from app.main import app

    with TestClient(app) as client:
        token = _token(client, "ws_revoked")
        assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204
        with client.websocket_connect("/api/v1/ws") as websocket:
            rejected = _auth(websocket, token)
            assert rejected["type"] == "error"

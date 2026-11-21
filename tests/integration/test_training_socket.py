"""lobby.join with mode training starts the practice range over the socket."""

from fastapi.testclient import TestClient

PASSWORD = "StrongTestPassword123!"


def _next_type(websocket, message_type: str) -> dict:
    for _ in range(80):
        message = websocket.receive_json()
        if message["type"] == message_type:
            return message
    raise AssertionError(f"Did not receive {message_type}")


def test_training_over_the_socket():
    from app.main import app

    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json={"username": "trainee", "password": PASSWORD}).status_code == 201
        token = client.post("/api/v1/auth/login", json={"username": "trainee", "password": PASSWORD}).json()["access_token"]
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json({"version": 1, "type": "auth", "sequence": 1, "payload": {"token": token}})
            _next_type(websocket, "auth.ok")
            websocket.send_json({"version": 1, "type": "lobby.join", "sequence": 2, "payload": {"mode": "training"}})
            ack = _next_type(websocket, "lobby.join.ack")
            assert ack["payload"] == {"ok": True, "detail": "Training started"}
            state = _next_type(websocket, "state")
            match = state["payload"]["match"]
            assert (match["mode"], match["phase"], state["payload"]["status"]) == ("training", "playing", "alive")
            websocket.send_json({"version": 1, "type": "match.forfeit", "sequence": 3, "payload": {}})
            left = _next_type(websocket, "match.forfeit.ack")
            assert left["payload"]["detail"] == "Left training"

"""Two accounts share a durable lobby, then each receives a live snapshot.

HTTP uses the pytest client, which points at the disposable test database.
The sockets ride the same process while that client's lifespan is running,
so the 20 Hz tick can push state.
"""

import asyncio
import json
from uuid import uuid4

PASSWORD = "StrongTestPassword123!"
_LIVE = {"queued", "countdown", "dropping", "alive"}


async def test_two_players_lobby_then_receive_a_snapshot(client):
    from app.core.config import settings
    from app.main import app

    assert settings.database_url.endswith("test_ros.db")

    host = await _account(client, f"fan_host_{uuid4().hex[:8]}")
    guest = await _account(client, f"fan_guest_{uuid4().hex[:8]}")

    opened = await client.post(
        "/api/v1/lobby",
        json={"code": f"FAN{uuid4().hex[:8]}", "max_players": 4},
        headers=host["headers"],
    )
    assert opened.status_code == 201
    lobby_id = opened.json()["id"]

    for player in (host, guest):
        joined = await client.post(f"/api/v1/lobby/{lobby_id}/members", headers=player["headers"])
        assert joined.status_code == 201
        ready = await client.post(
            f"/api/v1/lobby/{lobby_id}/ready",
            json={"ready": True},
            headers=player["headers"],
        )
        assert ready.status_code == 200
        assert ready.json()["ready"] is True

    roster = await client.get(f"/api/v1/lobby/{lobby_id}/members", headers=host["headers"])
    assert roster.status_code == 200
    assert len(roster.json()) == 2
    assert all(row["ready"] is True for row in roster.json())

    host_socket = await _open_socket(app)
    guest_socket = await _open_socket(app)
    try:
        host_id = await _authenticate(host_socket, host["token"])
        guest_id = await _authenticate(guest_socket, guest["token"])
        assert host_id != guest_id
        for socket, player_id in ((host_socket, host_id), (guest_socket, guest_id)):
            await _join_queue(socket)
            snapshot = await _live_snapshot(socket, player_id)
            assert snapshot["player_id"] == player_id
            assert snapshot["status"] in _LIVE or "match" in snapshot
    finally:
        await host_socket.close()
        await guest_socket.close()


async def _account(client, username: str) -> dict:
    created = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert created.status_code == 201
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    profile = await client.get("/api/v1/players/me", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["coin"] == 500
    assert body["diamond"] == 20
    assert body["equipped_skin"] == "recruit"
    return {"token": token, "headers": headers}


async def _authenticate(socket: "_Socket", token: str) -> str:
    await socket.send_json({"version": 1, "type": "auth", "sequence": 1, "payload": {"token": token}})
    welcome = await _until(socket, "auth.ok", 3)
    player_id = welcome["payload"]["player_id"]
    assert isinstance(player_id, str) and player_id
    return player_id


async def _join_queue(socket: "_Socket") -> None:
    await socket.send_json({"version": 1, "type": "lobby.join", "sequence": 2, "payload": {}})
    ack = await _until(socket, "lobby.join.ack", 3)
    assert ack["payload"]["ok"] is True


async def _live_snapshot(socket: "_Socket", player_id: str) -> dict:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 3
    last_status = None
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise AssertionError(f"no live snapshot; last status was {last_status}")
        message = await socket.next_json(remaining)
        if message["type"] != "state":
            continue
        payload = message["payload"]
        last_status = payload.get("status")
        if payload.get("player_id") != player_id:
            continue
        if payload.get("status") in _LIVE or "match" in payload:
            return payload


async def _until(socket: "_Socket", message_type: str, timeout: float) -> dict:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise AssertionError(message_type)
        message = await socket.next_json(remaining)
        if message["type"] == message_type:
            return message


class _Socket:
    def __init__(self, incoming: asyncio.Queue, outgoing: asyncio.Queue, task: asyncio.Task) -> None:
        self._incoming = incoming
        self._outgoing = outgoing
        self._task = task
        self._closed = False

    async def send_json(self, payload: dict) -> None:
        self._raise_if_dead()
        await self._incoming.put({"type": "websocket.receive", "text": json.dumps(payload, separators=(",", ":"))})

    async def next_json(self, timeout: float) -> dict:
        self._raise_if_dead()
        message = await asyncio.wait_for(self._outgoing.get(), timeout)
        if message["type"] == "websocket.close":
            raise AssertionError(f"socket closed with {message.get('code', 1000)}")
        if message["type"] != "websocket.send":
            raise AssertionError(f"unexpected frame {message['type']}")
        text = message.get("text")
        if not isinstance(text, str):
            raise AssertionError("expected a text frame")
        return json.loads(text)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._incoming.put({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(self._task, 2)
        except asyncio.TimeoutError:
            self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception:
            if not self._task.cancelled():
                raise

    def _raise_if_dead(self) -> None:
        if self._closed or not self._task.done():
            return
        self._task.result()


async def _open_socket(app) -> _Socket:
    incoming: asyncio.Queue = asyncio.Queue()
    outgoing: asyncio.Queue = asyncio.Queue()

    async def receive():
        return await incoming.get()

    async def send(message):
        await outgoing.put(message)

    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "path": "/api/v1/ws",
        "raw_path": b"/api/v1/ws",
        "root_path": "",
        "scheme": "ws",
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("testclient", 50000),
        "server": ["testserver", 80],
        "subprotocols": [],
        "state": {},
        "extensions": {"websocket.http.response": {}},
    }
    task = asyncio.create_task(app(scope, receive, send))
    await incoming.put({"type": "websocket.connect"})
    accepted = await asyncio.wait_for(outgoing.get(), 5)
    if accepted["type"] != "websocket.accept":
        task.cancel()
        raise AssertionError(f"socket was not accepted: {accepted['type']}")
    return _Socket(incoming, outgoing, task)

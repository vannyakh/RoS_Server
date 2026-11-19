"""Two authenticated sockets share one live match on the ASGI tick.

Damage and magazine size come from app.game.items. Speed, map size, and hit
radius come from app.game.rules. Queue, countdown, drop, and bot fill are
shortened on the running engine so two humans finish the tick without bots.
Those overrides do not change speed, damage, zone, or vehicle numbers.
"""

import json
import math
import time
from dataclasses import replace
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.game.items import WEAPONS
from app.game.rules import MatchRules
from app.game.state import Blocker

PASSWORD = "StrongTestPassword123!"
_PISTOL = WEAPONS["pistol"]


class _FrameTimeout(Exception):
    pass


def test_two_authenticated_clients_fight_one_match():
    from app.game.engine import game_engine
    from app.main import app

    saved = game_engine.rules
    rules = _two_human_rules(saved)
    with TestClient(app) as client:
        game_engine.rules = rules
        try:
            _play(client, rules)
        finally:
            game_engine.rules = saved


def _two_human_rules(current: MatchRules) -> MatchRules:
    rules = replace(
        current,
        bot_fill=0,
        max_players=2,
        queue_wait=30.0,
        countdown=0.0,
        drop_time=0.0,
        phase_duration=120.0,
        result_time=30.0,
        loot_count=0,
    )
    assert rules.speed == current.speed
    assert rules.map_size == current.map_size
    assert rules.hit_radius == current.hit_radius
    assert rules.zone_radii == current.zone_radii
    assert rules.zone_dps == current.zone_dps
    return rules


def _play(client: TestClient, rules: MatchRules) -> None:
    left_name = f"p1{uuid4().hex[:8]}"
    right_name = f"p2{uuid4().hex[:8]}"
    left_token = _token(client, left_name)
    right_token = _token(client, right_name)
    with client.websocket_connect("/api/v1/ws") as left_socket, client.websocket_connect("/api/v1/ws") as right_socket:
        left_id = _auth(left_socket, left_token)
        right_id = _auth(right_socket, right_token)
        sockets = {left_id: left_socket, right_id: right_socket}
        sequences = {left_id: 1, right_id: 1}
        for player_id in (left_id, right_id):
            _send(sockets[player_id], sequences, player_id, "lobby.join", {})
            ack, _states = _wait_ack(sockets[player_id], "lobby.join.ack")
            assert ack["payload"]["ok"] is True

        opened = _wait_state(left_socket, lambda payload: _both_playing(payload, left_id, right_id), 3)
        match_id = opened["match_id"]
        other = _wait_state(right_socket, lambda payload: payload.get("match_id") == match_id and payload.get("status") == "alive", 3)
        assert other["match_id"] == match_id
        assert opened["map_size"] == rules.map_size
        players = opened["match"]["players"]
        assert len(players) == 2
        assert all(item["bot"] is False for item in players)
        western = min(players, key=lambda item: (item["x"], item["player_id"]))
        eastern = max(players, key=lambda item: (item["x"], item["player_id"]))
        assert eastern["x"] - western["x"] <= _PISTOL["range"]
        assert abs(eastern["y"] - western["y"]) <= rules.hit_radius
        shooter_id = western["player_id"]
        victim_id = eastern["player_id"]
        shooter = sockets[shooter_id]
        victim = sockets[victim_id]

        playing = _wait_state(
            shooter,
            lambda payload: payload.get("player_id") == shooter_id and payload.get("match", {}).get("phase") == "playing",
            2,
        )
        assert playing["match"]["self"]["weapon"] == "pistol"
        assert playing["match"]["self"]["mag"] == _PISTOL["mag"]
        start_x = playing["x"]
        start_y = playing["y"]

        sent = time.monotonic()
        _send(shooter, sequences, shooter_id, "player.input", {"move_x": -1, "move_y": 0, "aim_x": 1, "aim_y": 0})
        move_ack, move_states = _wait_ack(shooter, "player.input.ack")
        moved = _after_tick(move_states, move_ack["payload"]["tick"])
        moved.extend(_collect_states(shooter, move_ack["payload"]["tick"], lambda payload: start_x - payload["x"] >= 0.4, 2))
        assert moved, "the server did not move the player"
        sample = moved[-1]
        elapsed = time.monotonic() - sent
        delta = start_x - sample["x"]
        assert delta >= 0.4
        assert delta <= rules.speed * elapsed + rules.speed * 0.05 + 0.02
        assert 0 <= sample["x"] <= rules.map_size
        assert 0 <= sample["y"] <= rules.map_size
        assert sample["y"] == start_y

        _send(shooter, sequences, shooter_id, "player.input", {"move_x": 0, "move_y": 0, "aim_x": 1, "aim_y": 0})
        stop_ack, stop_states = _wait_ack(shooter, "player.input.ack")
        settled = _stable_position(shooter, stop_ack["payload"]["tick"], stop_states)
        blocker = Blocker(settled["x"] - 3, settled["y"] + 0.2, settled["x"] + 3, settled["y"] + 6)
        _add_blocker(client, shooter_id, blocker)
        _send(shooter, sequences, shooter_id, "player.input", {"move_x": 0, "move_y": 1, "aim_x": 1, "aim_y": 0})
        blocked_ack, blocked_states = _wait_ack(shooter, "player.input.ack")
        blocked = _after_tick(blocked_states, blocked_ack["payload"]["tick"])
        blocked.extend(_collect_states(shooter, blocked_ack["payload"]["tick"], lambda _payload: False, 0.45))
        assert blocked, "the tick did not publish while the player pushed into the blocker"
        assert all(item["y"] == settled["y"] for item in blocked)
        assert all(item["y"] < blocker.minimum_y for item in blocked)
        assert all(0 <= item["x"] <= rules.map_size for item in blocked)

        _send(shooter, sequences, shooter_id, "player.input", {"move_x": 0, "move_y": 0, "aim_x": 1, "aim_y": 0})
        _wait_ack(shooter, "player.input.ack")
        health = _player(settled, victim_id)["health"]
        shots = math.ceil(health / _PISTOL["damage"])
        final = None
        for shot in range(1, shots + 1):
            _send(shooter, sequences, shooter_id, "player.action", {"action": "shoot"})
            ack, states = _wait_ack(shooter, "player.action.ack")
            assert ack["payload"]["ok"] is True
            expected_health = 0.0 if shot == shots else round(health - _PISTOL["damage"] * shot, 1)
            detail = "Eliminated" if shot == shots else "Hit"
            assert ack["payload"]["detail"] == detail

            def landed(payload: dict, expected: float = expected_health) -> bool:
                return _player(payload, victim_id)["health"] == expected and payload["match"]["self"]["mag"] == _PISTOL["mag"] - shot

            found = next((item for item in states if landed(item)), None)
            if found is None:
                found = _wait_state(shooter, landed, 2)
            final = found
            if shot < shots:
                time.sleep(_PISTOL["cooldown"] + 0.15)
        assert final is not None
        assert final["status"] == "winner"
        assert final["kills"] == 1
        assert final["match"]["phase"] == "ended"
        assert final["match"]["winner_id"] == shooter_id
        victim_row = _player(final, victim_id)
        assert victim_row["status"] == "eliminated"
        assert victim_row["health"] == 0
        assert final["match"]["self"]["mag"] == _PISTOL["mag"] - shots

        victim_view = _wait_state(
            victim,
            lambda payload: payload.get("status") == "eliminated" and payload.get("health") == 0 and payload.get("match", {}).get("phase") == "ended",
            3,
        )
        assert victim_view["match"]["winner_id"] == shooter_id
        assert victim_view["match_id"] == match_id

        winner_token = left_token if shooter_id == left_id else right_token
        loser_token = right_token if winner_token is left_token else left_token
        winner_profile, loser_profile = _saved_profiles(client, winner_token, loser_token)
        assert winner_profile["kills"] == 1
        assert winner_profile["wins"] == 1
        assert winner_profile["matches_played"] == 1
        assert loser_profile["kills"] == 0
        assert loser_profile["wins"] == 0
        assert loser_profile["matches_played"] == 1


def _token(client: TestClient, username: str) -> str:
    created = client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD})
    assert created.status_code == 201
    logged_in = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _auth(websocket, token: str) -> str:
    websocket.send_json({"version": 1, "type": "auth", "sequence": 1, "payload": {"token": token}})
    welcome, _states = _wait_ack(websocket, "auth.ok", timeout=3)
    player_id = welcome["payload"]["player_id"]
    assert isinstance(player_id, str) and player_id
    return player_id


def _send(websocket, sequences: dict[str, int], player_id: str, message_type: str, payload: dict) -> None:
    sequences[player_id] += 1
    websocket.send_json(
        {"version": 1, "type": message_type, "sequence": sequences[player_id], "payload": payload}
    )


def _both_playing(payload: dict, first_id: str, second_id: str) -> bool:
    match = payload.get("match") or {}
    ids = {item["player_id"] for item in match.get("players") or []}
    return payload.get("status") == "alive" and match.get("phase") == "playing" and ids == {first_id, second_id}


def _player(payload: dict, player_id: str) -> dict:
    for item in payload["match"]["players"]:
        if item["player_id"] == player_id:
            return item
    raise AssertionError("player missing from the server snapshot")


def _after_tick(states: list[dict], tick: int) -> list[dict]:
    return [item for item in states if item.get("tick", 0) > tick]


def _add_blocker(client: TestClient, player_id: str, blocker: Blocker) -> None:
    from app.game.engine import game_engine

    async def _place() -> None:
        async with game_engine._lock:
            player = game_engine.world.players[player_id]
            match = game_engine.world.matches[player.match_id]
            match.blockers.append(blocker)

    client.portal.call(_place)


def _saved_profiles(client: TestClient, winner_token: str, loser_token: str) -> tuple[dict, dict]:
    deadline = time.monotonic() + 3
    winner = loser = {}
    while time.monotonic() < deadline:
        winner = _profile(client, winner_token)
        loser = _profile(client, loser_token)
        if winner["kills"] == 1 and winner["wins"] == 1 and winner["matches_played"] == 1 and loser["matches_played"] == 1:
            return winner, loser
        time.sleep(0.1)
    return winner, loser


def _profile(client: TestClient, token: str) -> dict:
    response = client.get("/api/v1/players/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    return {"kills": body["kills"], "wins": body["wins"], "matches_played": body["matches_played"]}


def _stable_position(websocket, tick: int, already: list[dict]) -> dict:
    previous = None
    for payload in _after_tick(already, tick):
        if previous is not None and previous["x"] == payload["x"] and previous["y"] == payload["y"]:
            return payload
        previous = payload
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        message = _receive(websocket, min(1.0, deadline - time.monotonic()))
        if message["type"] != "state" or message["payload"].get("tick", 0) <= tick:
            continue
        payload = message["payload"]
        if previous is not None and previous["x"] == payload["x"] and previous["y"] == payload["y"]:
            return payload
        previous = payload
    raise AssertionError("the player did not stop")


def _collect_states(websocket, tick: int, done, seconds: float) -> list[dict]:
    found: list[dict] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            message = _receive(websocket, min(0.5, max(0.05, deadline - time.monotonic())))
        except _FrameTimeout:
            break
        if message["type"] == "error":
            raise AssertionError(message["payload"]["detail"])
        if message["type"] != "state" or message["payload"].get("tick", 0) <= tick:
            continue
        found.append(message["payload"])
        if done(message["payload"]):
            break
    return found


def _wait_state(websocket, predicate, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        message = _receive(websocket, min(1.0, max(0.05, deadline - time.monotonic())))
        if message["type"] == "error":
            raise AssertionError(message["payload"]["detail"])
        if message["type"] != "state":
            continue
        last = message["payload"]
        if predicate(last):
            return last
    raise AssertionError(f"snapshot condition was not met: {last}")


def _wait_ack(websocket, message_type: str, timeout: float = 2.0) -> tuple[dict, list[dict]]:
    deadline = time.monotonic() + timeout
    states: list[dict] = []
    while time.monotonic() < deadline:
        message = _receive(websocket, min(1.0, max(0.05, deadline - time.monotonic())))
        if message["type"] == "error":
            raise AssertionError(message["payload"]["detail"])
        if message["type"] == "state":
            states.append(message["payload"])
            continue
        if message["type"] == message_type:
            return message, states
    raise AssertionError(message_type)


def _receive(websocket, timeout: float) -> dict:
    async def _recv() -> dict:
        with anyio.fail_after(timeout):
            return await websocket._send_rx.receive()

    try:
        message = websocket.portal.call(_recv)
    except TimeoutError as exc:
        raise _FrameTimeout from exc
    if message["type"] == "websocket.close":
        raise WebSocketDisconnect(code=message.get("code", 1000))
    text = message.get("text")
    if not isinstance(text, str):
        raise AssertionError("expected a text frame")
    return json.loads(text)

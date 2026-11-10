"""Local world, movement, vehicle, and result rules. These are not original RoS values."""

import pytest

from app.game.engine import GameEngine
from app.game.items import VEHICLES, WEAPONS
from app.game.rules import MatchRules
from app.networking.protocol import parse_action


def _rules(**overrides) -> MatchRules:
    values = {
        "bot_fill": 0,
        "queue_wait": 0,
        "countdown": 0,
        "drop_time": 0,
        "phase_duration": 100,
        "result_time": 100,
        "max_players": 4,
    }
    values.update(overrides)
    return MatchRules(**values)


async def test_on_foot_movement_uses_the_server_speed():
    engine = GameEngine(_rules())
    await engine.connect("alpha")
    await engine.join_queue("alpha")
    await engine.step(0.05)
    player = engine.world.players["alpha"]
    start = player.x
    await engine.set_input("alpha", 1, 0)
    await engine.step(1)
    assert player.x - start == pytest.approx(5.0)
    assert player.vehicle is None
    view = (await engine.step(0))[0]
    assert view["vehicle"] is None
    assert view["health"] == 100.0


async def test_vehicle_changes_speed_and_blocks_shooting():
    engine = GameEngine(_rules())
    await engine.connect("alpha")
    await engine.join_queue("alpha")
    await engine.step(0.05)
    player = engine.world.players["alpha"]
    match = engine.world.matches[player.match_id]
    vehicle = match.vehicles[0]
    assert vehicle.kind == "buggy"
    vehicle.x = 40.0
    vehicle.y = 40.0
    player.x = vehicle.x
    player.y = vehicle.y

    boarded, detail = await engine.perform("alpha", "board", None, None)
    assert boarded, detail
    assert player.vehicle == vehicle.vehicle_id
    assert vehicle.occupant == "alpha"

    start = player.x
    await engine.set_input("alpha", 1, 0)
    await engine.step(1)
    assert player.x - start == pytest.approx(VEHICLES["buggy"]["speed"])
    assert vehicle.x == pytest.approx(player.x)

    shot, shot_detail = await engine.perform("alpha", "shoot", None, None)
    assert not shot
    assert shot_detail == "Leave the vehicle first"

    left, left_detail = await engine.perform("alpha", "exit", None, None)
    assert left, left_detail
    assert player.vehicle is None
    assert vehicle.occupant is None
    start = player.x
    await engine.step(1)
    assert player.x - start == pytest.approx(5.0)


async def test_countdown_uses_the_match_clock():
    engine = GameEngine(_rules(countdown=1, drop_time=2))
    await engine.connect("alpha")
    await engine.join_queue("alpha")
    await engine.step(0.05)
    match = next(iter(engine.world.matches.values()))
    assert match.phase == "countdown"
    await engine.step(1)
    assert match.phase == "dropping"


async def test_results_record_placement_and_kills_only():
    engine = GameEngine(_rules())
    for player_id in ("alpha", "bravo"):
        await engine.connect(player_id)
        await engine.join_queue(player_id)
    await engine.step(0.05)
    alpha = engine.world.players["alpha"]
    bravo = engine.world.players["bravo"]
    alpha.x, alpha.y = 10.0, 10.0
    bravo.x, bravo.y = 12.0, 10.0
    alpha.aim_x, alpha.aim_y = 1.0, 0.0
    shots = 0
    while bravo.status != "eliminated" and shots < 8:
        ok, detail = await engine.perform("alpha", "shoot", None, None)
        assert ok, detail
        shots += 1
        await engine.step(WEAPONS["pistol"]["cooldown"])
    assert bravo.status == "eliminated"
    match = engine.world.matches[alpha.match_id]
    assert match.phase == "ended"
    assert match.winner_id == "alpha"
    results = {item.player_id: item for item in await engine.take_results()}
    assert results["alpha"].placement == 1
    assert results["alpha"].kills == 1
    assert results["alpha"].win is True
    assert results["bravo"].placement == 2
    assert results["bravo"].kills == 0
    assert not hasattr(results["alpha"], "experience")


def test_board_and_exit_are_known_actions():
    assert parse_action({"action": "board"}).action == "board"
    assert parse_action({"action": "exit"}).action == "exit"

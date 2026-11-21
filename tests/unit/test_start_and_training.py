"""Warm-up island before the plane, and the training range.

Independent design, not original Rules of Survival values.
"""

import math

from app.game.engine import GameEngine
from app.game.rules import MatchRules
from app.game.simulate import snapshot


def _rules(**overrides) -> MatchRules:
    values = dict(bot_fill=0, queue_wait=0, countdown=10, drop_time=5, phase_duration=100, result_time=100)
    values.update(overrides)
    return MatchRules(**values)


async def _queue(engine: GameEngine, *player_ids: str):
    for player_id in player_ids:
        ok, _ = await engine.join_queue(player_id)
        assert ok
    await engine.step(0.05)
    return next(iter(engine.world.matches.values()))


async def test_warmup_island_players_walk_unarmed_and_see_the_countdown():
    engine = GameEngine(_rules(warmup_island=True, island_radius=20))
    match = await _queue(engine, "alpha", "bravo")
    alpha = engine.world.players["alpha"]
    assert match.phase == "countdown"
    assert (alpha.on_plane, alpha.z, alpha.weapon, alpha.inventory) == (False, 0.0, None, {})
    assert math.hypot(alpha.x - 100, alpha.y - 100) <= 20
    view = snapshot(engine.world, alpha, engine.rules)["match"]
    assert (view["phase"], view["total"], view["mode"]) == ("countdown", 2, "standard")
    assert view["starts_in"] == 9.9
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert not ok  # nothing to shoot with before the plane
    start = alpha.x
    await engine.set_input("alpha", 1, 0)
    await engine.step(1.0)
    assert alpha.x > start


async def test_warmup_ends_on_the_plane_with_a_starter_kit():
    engine = GameEngine(_rules(warmup_island=True, countdown=2))
    match = await _queue(engine, "alpha", "bravo")
    await engine.step(2.0)
    assert match.phase == "dropping"
    alpha = engine.world.players["alpha"]
    assert (alpha.on_plane, alpha.z, alpha.status, alpha.weapon) == (True, 40.0, "dropping", "pistol")
    assert snapshot(engine.world, alpha, engine.rules)["match"]["starts_in"] is None
    ok, detail = await engine.perform("alpha", "jump", None, None)
    assert ok and detail == "Jumped"


async def test_without_warmup_island_the_old_flow_is_unchanged():
    engine = GameEngine(_rules())
    await _queue(engine, "alpha", "bravo")
    alpha = engine.world.players["alpha"]
    assert (alpha.on_plane, alpha.z, alpha.weapon) == (True, 40.0, "pistol")


async def _training(engine: GameEngine):
    ok, detail = await engine.join_training("human")
    assert ok and detail == "Training started"
    return next(iter(engine.world.matches.values()))


async def test_training_gives_a_kit_and_never_ends_or_shrinks():
    engine = GameEngine(_rules(phase_duration=1))
    match = await _training(engine)
    human = engine.world.players["human"]
    assert match.mode == "training" and match.phase == "playing"
    assert (human.status, human.weapon, human.armor) == ("alive", "rifle", 1)
    assert len(match.player_ids) == 1 + engine.rules.training_dummies
    await engine.step(30.0)
    assert match.phase == "playing" and match.zone_radius > 200
    assert human.health == 100.0
    assert snapshot(engine.world, human, engine.rules)["match"]["mode"] == "training"


async def test_training_dummies_respawn_and_count_kills_but_nothing_is_recorded():
    engine = GameEngine(_rules())
    match = await _training(engine)
    human = engine.world.players["human"]
    dummy = engine.world.players[match.player_ids[1]]
    spawn = (dummy.x, dummy.y)
    human.x, human.y = dummy.x - 10, dummy.y
    human.aim_x, human.aim_y = 1.0, 0.0
    for _ in range(40):
        ok, detail = await engine.perform("human", "shoot", None, None)
        if detail == "Eliminated":
            break
        if detail == "Reload":
            await engine.perform("human", "reload", None, None)
            await engine.step(2.5)
        await engine.step(0.2)
    assert detail == "Eliminated"
    assert (dummy.status, dummy.health, (dummy.x, dummy.y)) == ("alive", 100.0, spawn)
    assert human.kills == 1
    kill = next(event for event in match.events if event["kind"] == "elimination")
    assert (kill["cause"], kill["weapon"]) == ("training", "rifle")
    assert match.phase == "playing"
    assert await engine.take_results() == []


async def test_training_player_who_dies_respawns_with_a_fresh_kit():
    engine = GameEngine(_rules())
    match = await _training(engine)
    human = engine.world.players["human"]
    from app.game.simulate import _eliminate

    human.inventory.clear()
    _eliminate(engine.world, match, human, None, "test")
    assert (human.status, human.health, human.weapon) == ("alive", 100.0, "rifle")
    assert human.inventory["medium"] == 120


async def test_leaving_training_ends_it_and_allows_a_real_queue():
    engine = GameEngine(_rules())
    await _training(engine)
    ok, detail = await engine.join_training("human")
    assert not ok and detail == "Already in a match"
    ok, detail = await engine.forfeit("human")
    assert ok and detail == "Left training"
    assert engine.world.matches == {}
    assert [pid for pid in engine.world.players if pid.startswith("bot-")] == []
    human = engine.world.players["human"]
    assert (human.status, human.match_id, human.armor) == ("roaming", None, 0)
    ok, _ = await engine.join_queue("human")
    assert ok

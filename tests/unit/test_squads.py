"""Squads: knock-down, bleed-out, revive, friendly fire, team win.

These numbers are this server's independent design, not original Rules of Survival values.
"""

from app.game.engine import GameEngine
from app.game.rules import MatchRules
from app.game.simulate import _eliminate


def _rules(**overrides) -> MatchRules:
    values = dict(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100, result_time=100)
    values.update(overrides)
    return MatchRules(**values)


async def _squad_match(engine: GameEngine, *others: str):
    for player_id in ("a1", "a2"):
        await engine.set_team(player_id, "red")
    for player_id in ("a1", "a2", *others):
        ok, _detail = await engine.join_queue(player_id)
        assert ok
    await engine.step(0.05)
    players = engine.world.players
    # Fixed layout so nobody stands in a line of fire: a1 and a2 together, the enemy ahead of them.
    for player_id, (x, y) in {"a1": (50, 50), "a2": (50, 56), "enemy": (60, 50)}.items():
        if player_id in players:
            players[player_id].x, players[player_id].y = x, y
    return next(iter(engine.world.matches.values()))


def _aim(engine, shooter: str, target: str) -> None:
    s, t = engine.world.players[shooter], engine.world.players[target]
    s.aim_x, s.aim_y = t.x - s.x, t.y - s.y


async def _knock_a1(engine: GameEngine) -> None:
    engine.world.players["a1"].health = 10
    _aim(engine, "enemy", "a1")
    ok, detail = await engine.perform("enemy", "shoot", None, None)
    assert ok and detail == "Knocked"


async def test_downed_player_with_a_living_teammate_is_knocked_not_eliminated():
    engine = GameEngine(_rules())
    match = await _squad_match(engine, "enemy")
    a1 = engine.world.players["a1"]
    await _knock_a1(engine)
    assert (a1.status, a1.health, a1.bleed_left) == ("knocked", 40.0, 30.0)
    assert engine.world.players["enemy"].kills == 0
    ok, detail = await engine.perform("a1", "shoot", None, None)
    assert not ok and detail == "Knocked down"
    start = a1.x
    await engine.set_input("a1", 1, 0)
    await engine.step(1.0)
    assert a1.x == start + 1.5  # crawling
    assert any(event["kind"] == "knock" for event in engine._event_log)
    assert match.phase == "playing"


async def test_finishing_a_knocked_player_credits_the_kill():
    engine = GameEngine(_rules())
    await _squad_match(engine, "enemy")
    a1 = engine.world.players["a1"]
    await _knock_a1(engine)
    for _ in range(4):
        await engine.step(0.4)
        await engine.perform("enemy", "shoot", None, None)
    assert a1.status == "eliminated"
    assert engine.world.players["enemy"].kills == 1


async def test_knocked_player_bleeds_out_and_credits_the_knocker():
    engine = GameEngine(_rules(bleed_time=3))
    match = await _squad_match(engine, "enemy")
    a1, a2 = engine.world.players["a1"], engine.world.players["a2"]
    a2.x, a2.y = 190, 190
    await _knock_a1(engine)
    await engine.step(3.1)
    assert a1.status == "eliminated"
    assert engine.world.players["enemy"].kills == 1
    assert match.kills["enemy"] == 1


async def test_teammate_revives_a_knocked_player():
    engine = GameEngine(_rules(revive_time=2))
    match = await _squad_match(engine, "enemy")
    a1, a2 = engine.world.players["a1"], engine.world.players["a2"]
    await _knock_a1(engine)
    a2.x, a2.y = a1.x + 1, a1.y
    ok, detail = await engine.perform("a2", "revive", None, None)
    assert ok and detail == "Reviving"
    await engine.step(1.0)
    assert a1.status == "knocked" and a2.revive_progress == 1.0
    await engine.step(1.05)
    assert (a1.status, a1.health) == ("alive", 30.0)
    assert a2.reviving is None
    assert match.phase == "playing"


async def test_moving_cancels_a_revive_and_enemies_cannot_revive():
    engine = GameEngine(_rules(revive_time=2))
    await _squad_match(engine, "enemy")
    a1, a2, enemy = (engine.world.players[p] for p in ("a1", "a2", "enemy"))
    await _knock_a1(engine)
    enemy.x, enemy.y = a1.x, a1.y
    ok, detail = await engine.perform("enemy", "revive", None, None)
    assert not ok and detail == "No teammates"
    a2.x, a2.y = a1.x + 1, a1.y
    await engine.perform("a2", "revive", None, None)
    await engine.set_input("a2", 1, 0)
    await engine.step(0.5)
    assert a2.reviving is None and a1.status == "knocked"


async def test_teammates_do_not_hurt_each_other():
    engine = GameEngine(_rules())
    await _squad_match(engine, "enemy")
    a1, a2 = engine.world.players["a1"], engine.world.players["a2"]
    a2.x, a2.y = a1.x + 5, a1.y
    engine.world.players["enemy"].x = 150
    a1.aim_x, a1.aim_y = 1.0, 0.0
    ok, detail = await engine.perform("a1", "shoot", None, None)
    assert ok and detail == "Missed" and a2.health == 100


async def test_last_squad_standing_wins_together():
    engine = GameEngine(_rules())
    match = await _squad_match(engine, "enemy")
    a1, a2, enemy = (engine.world.players[p] for p in ("a1", "a2", "enemy"))
    enemy.health = 10
    a1.x, a1.y, a1.aim_x, a1.aim_y = enemy.x - 5, enemy.y, 1.0, 0.0
    ok, detail = await engine.perform("a1", "shoot", None, None)
    assert ok and detail == "Eliminated"
    assert match.phase == "ended"
    assert sorted(match.winner_ids) == ["a1", "a2"]
    assert a1.status == a2.status == "winner"
    results = {r.player_id: r for r in await engine.take_results()}
    assert results["a1"].win and results["a2"].win
    assert results["enemy"].placement == 2


async def test_knocked_player_is_eliminated_when_the_rest_of_the_squad_dies():
    engine = GameEngine(_rules())
    match = await _squad_match(engine, "enemy")
    a1, a2 = engine.world.players["a1"], engine.world.players["a2"]
    await _knock_a1(engine)
    _eliminate(engine.world, match, a2, "enemy", "shot")
    await engine.step(0.05)
    assert a1.status == "eliminated"
    assert match.phase == "ended" and match.winner_id == "enemy"


async def test_auto_squads_group_queued_players():
    engine = GameEngine(_rules(team_size=2))
    for player_id in ("p1", "p2", "p3"):
        await engine.join_queue(player_id)
    await engine.step(0.05)
    teams = {p: engine.world.players[p].team_id for p in ("p1", "p2", "p3")}
    assert teams["p1"] == teams["p2"] != teams["p3"]

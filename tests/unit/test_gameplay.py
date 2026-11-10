"""Match flow: queue, combat, loot, zone, and results."""

from app.game.engine import GameEngine
from app.game.rules import MatchRules


def _rules(**overrides) -> MatchRules:
    values = dict(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100, result_time=100)
    values.update(overrides)
    return MatchRules(**values)


async def _start(engine: GameEngine, *player_ids: str) -> None:
    for player_id in player_ids:
        ok, _detail = await engine.join_queue(player_id)
        assert ok
    await engine.step(0.05)
    match = next(iter(engine.world.matches.values()))
    assert match.phase == "playing"


async def test_queue_fills_the_match_with_bots():
    engine = GameEngine(MatchRules(queue_wait=0, countdown=10, bot_fill=7))
    ok, detail = await engine.join_queue("human")
    assert ok and detail == "Queued"
    await engine.step(0.05)
    match = next(iter(engine.world.matches.values()))
    assert match.phase == "countdown"
    assert len(match.player_ids) == 8
    assert sum(engine.world.players[pid].is_bot for pid in match.player_ids) == 7


async def test_player_moves_inside_a_match():
    engine = GameEngine(_rules())
    await _start(engine, "human")
    start = engine.world.players["human"].x
    await engine.set_input("human", 1, 0)
    await engine.step(1)
    assert engine.world.players["human"].x == start + 5


async def test_shot_eliminates_the_last_opponent_and_records_the_win():
    engine = GameEngine(_rules())
    await _start(engine, "alpha", "bravo")
    for _ in range(4):
        ok, detail = await engine.perform("alpha", "shoot", None, None)
        assert ok and detail == "Hit"
        await engine.step(0.4)
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert ok and detail == "Eliminated"
    match = next(iter(engine.world.matches.values()))
    assert match.phase == "ended"
    assert match.winner_id == "alpha"
    assert engine.world.players["bravo"].status == "eliminated"
    results = {result.player_id: result for result in await engine.take_results()}
    assert results["alpha"].win is True
    assert results["alpha"].kills == 1
    assert results["bravo"].win is False


async def test_pickup_and_heal():
    engine = GameEngine(_rules())
    await _start(engine, "human")
    player = engine.world.players["human"]
    bandage = next(node for node in next(iter(engine.world.matches.values())).loot if node.item_id == "bandage")
    player.x = bandage.x
    player.y = bandage.y
    ok, detail = await engine.perform("human", "pickup", bandage.loot_id, None)
    assert ok and detail == "Picked up bandage"
    player.health = 40
    ok, detail = await engine.perform("human", "use", None, "bandage")
    assert ok and detail == "Healed"
    assert player.health == 60


async def test_zone_damages_a_player_outside_it():
    engine = GameEngine(_rules())
    await _start(engine, "human")
    player = engine.world.players["human"]
    player.x = 0
    player.y = 0
    await engine.step(1)
    assert player.health == 99


async def test_leave_lobby_before_the_match_starts():
    engine = GameEngine(MatchRules(queue_wait=30, bot_fill=0))
    await engine.join_queue("human")
    ok, detail = await engine.leave_queue("human")
    assert ok and detail == "Left the lobby"
    await engine.step(1)
    assert engine.world.matches == {}

from app.game.engine import GameEngine
from app.game.rules import MatchRules


async def test_two_players_can_request_a_match():
    engine = GameEngine(MatchRules(bot_fill=0, queue_wait=0, countdown=10))
    assert (await engine.join_queue("alpha"))[0] is True
    assert (await engine.join_queue("bravo"))[0] is True
    await engine.step(0.05)
    match = next(iter(engine.world.matches.values()))
    assert set(match.player_ids) == {"alpha", "bravo"}
    assert match.phase == "countdown"

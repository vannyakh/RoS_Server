from app.game.engine import GameEngine
from app.game.items import WEAPONS
from app.game.rules import MatchRules


async def test_pistol_damage_is_the_local_rule_not_an_original_table():
    assert WEAPONS["pistol"]["damage"] == 22.0
    engine = GameEngine(MatchRules(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100))
    await engine.join_queue("alpha")
    await engine.join_queue("bravo")
    await engine.step(0.05)
    alpha = engine.world.players["alpha"]
    bravo = engine.world.players["bravo"]
    bravo.x = alpha.x + 2
    bravo.y = alpha.y
    alpha.aim_x = 1
    alpha.aim_y = 0
    before = bravo.health
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert ok is True and detail == "Hit"
    assert engine.world.players["bravo"].health == before - 22.0

from app.game.engine import GameEngine
from app.game.rules import MatchRules


async def test_player_can_pick_up_nearby_loot():
    engine = GameEngine(MatchRules(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100))
    assert (await engine.join_queue("human"))[0] is True
    await engine.step(0.05)
    player = engine.world.players["human"]
    # Gear is worn, not stacked, and a second pistol has no free slot, so take a plain stackable item.
    node = next(n for n in engine.world.matches[player.match_id].loot if n.item_id in {"light", "medium", "heavy", "bandage", "medkit"})
    player.x = node.x
    player.y = node.y
    ok, detail = await engine.perform("human", "pickup", node.loot_id, None)
    assert ok is True
    assert player.inventory[node.item_id] >= 1
    assert detail.startswith("Picked up")

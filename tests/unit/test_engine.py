"""Movement stays inside the in-memory engine."""

from app.game.engine import GameEngine


async def test_step_applies_input_without_a_database():
    engine = GameEngine()
    await engine.set_input("player-1", 1, 0)
    snapshots = await engine.step(1)
    assert engine.world.players["player-1"].x == 5
    assert snapshots[0]["player_id"] == "player-1"
    assert snapshots[0]["tick"] == 1

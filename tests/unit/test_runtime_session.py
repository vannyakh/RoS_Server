"""Two-player session: movement stops on a blocker, and the server applies the shot."""

from app.game.state import Blocker
from game_runtime.session import AuthoritativeSession


async def test_a_blocker_stops_forward_movement():
    session = AuthoritativeSession()
    await session.start("alpha", "bravo")
    alpha = session.engine.world.players["alpha"]
    start = alpha.x
    session.add_blocker(Blocker(start + 1, alpha.y - 2, start + 8, alpha.y + 2))
    await session.command("alpha", 1, 0)
    await session.tick(1)
    assert alpha.x == start


async def test_the_server_applies_damage_and_records_the_winner():
    session = AuthoritativeSession()
    await session.start("alpha", "bravo")
    for _ in range(4):
        ok, detail = await session.fire("alpha")
        assert ok and detail == "Hit"
        await session.tick(0.4)
    ok, detail = await session.fire("alpha")
    assert ok and detail == "Eliminated"
    assert session.engine.world.players["bravo"].status == "eliminated"
    results = {item.player_id: item for item in await session.results()}
    assert results["alpha"].win is True
    assert results["alpha"].kills == 1
    assert results["bravo"].win is False


async def test_a_client_cannot_report_its_own_hit():
    session = AuthoritativeSession()
    await session.start("alpha", "bravo")
    before = session.engine.world.players["bravo"].health
    ok, detail = await session.engine.perform("alpha", "damage", None, None)
    assert ok is False
    assert detail == "Unknown action"
    assert session.engine.world.players["bravo"].health == before

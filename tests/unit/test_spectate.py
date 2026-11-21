"""Spectator frames show every combatant and keep match events after the tick clears them."""

import asyncio

from app.game.engine import GameEngine
from app.game.rules import default_rules
from app.game.spectate import spectator_frame
from app.game.state import Blocker, Match, PlayerState, WorldState


def _world() -> tuple[WorldState, Match]:
    world = WorldState()
    world.players["a"] = PlayerState(player_id="a", x=10.5, y=20.25, nickname="Raven", status="alive", kills=2, match_id="m1")
    world.players["b"] = PlayerState(player_id="b", x=30, y=40, is_bot=True, status="eliminated", health=0, match_id="m1")
    match = Match(match_id="m1", player_ids=["a", "b"], phase="playing", blockers=[Blocker(1, 2, 3, 4, "rock")])
    world.matches["m1"] = match
    return world, match


def test_frame_lists_every_combatant_and_sends_cover_once():
    world, match = _world()
    frame = spectator_frame(world, match, default_rules(), static=True)
    assert (frame["alive"], frame["total"]) == (1, 2)
    assert {player["player_id"] for player in frame["players"]} == {"a", "b"}
    raven = next(player for player in frame["players"] if player["player_id"] == "a")
    assert (raven["x"], raven["nickname"], raven["kills"]) == (10.5, "Raven", 2)
    assert frame["blockers"][0]["kind"] == "rock"
    assert "blockers" not in spectator_frame(world, match, default_rules(), static=False)


def test_engine_keeps_events_for_spectators():
    async def run():
        engine = GameEngine()
        world, match = _world()
        engine.world = world
        match.events.append({"kind": "elimination", "player_id": "b", "killer_id": "a", "cause": "shot"})
        await engine.step(0.0)
        assert match.events == []
        everything = await engine.spectate(None, 0, static=False)
        assert any(event["kind"] == "elimination" and event["match_id"] == "m1" for event in everything["events"])
        later = await engine.spectate("m1", everything["tick"], static=False)
        assert later["events"] == []
        assert (await engine.spectate("missing", 0, static=False))["found"] is False

    asyncio.run(run())

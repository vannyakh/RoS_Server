"""Headless match session over the in-memory engine. This module does not open HTTP or SQL."""

from app.game.engine import GameEngine
from app.game.rules import MatchRules
from app.game.state import Blocker, MatchResult


def prototype_rules() -> MatchRules:
    return MatchRules(
        bot_fill=0,
        queue_wait=0,
        countdown=0,
        drop_time=0,
        phase_duration=100,
        result_time=100,
        loot_count=0,
    )


class AuthoritativeSession:
    """Two players, one world, server-owned positions and damage."""

    def __init__(self, rules: MatchRules | None = None) -> None:
        self.engine = GameEngine(rules or prototype_rules())

    async def start(self, left: str, right: str) -> str:
        for player_id in (left, right):
            await self.engine.connect(player_id)
            ok, detail = await self.engine.join_queue(player_id)
            if not ok:
                raise RuntimeError(detail)
        await self.engine.step(0.05)
        match = next(iter(self.engine.world.matches.values()))
        if match.phase != "playing":
            raise RuntimeError(f"Match stayed in {match.phase}")
        return match.match_id

    def add_blocker(self, blocker: Blocker) -> None:
        match = next(iter(self.engine.world.matches.values()))
        match.blockers.append(blocker)

    async def command(self, player_id: str, move_x: float, move_y: float, aim_x: float = 1.0, aim_y: float = 0.0) -> int:
        return await self.engine.set_input(player_id, move_x, move_y, aim_x, aim_y)

    async def fire(self, player_id: str) -> tuple[bool, str]:
        return await self.engine.perform(player_id, "shoot", None, None)

    async def tick(self, dt: float = 0.05) -> list[dict]:
        return await self.engine.step(dt)

    async def results(self) -> list[MatchResult]:
        return await self.engine.take_results()

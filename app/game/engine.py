"""In-memory world. Movement and combat advance only from the tick or a player action."""

import asyncio
from collections import deque

from app.game.rules import MatchRules, default_rules
from app.game.simulate import (
    apply_action,
    forfeit,
    leave_queue,
    lobby_view,
    match_view,
    matches_view,
    queue_player,
    simulate,
    snapshot,
)
from app.game.spectate import spectator_frame
from app.game.state import MatchResult, PlayerState, WorldState

EVENT_LOG_SIZE = 2000
EVENTS_PER_FRAME = 200


class GameEngine:
    def __init__(self, rules: MatchRules | None = None) -> None:
        self.rules = rules or default_rules()
        self.world = WorldState()
        self._lock = asyncio.Lock()
        # Match events for spectators: copied each tick before the per-tick list is cleared.
        self._event_log: deque[dict] = deque(maxlen=EVENT_LOG_SIZE)

    def reset_state(self) -> None:
        self.world = WorldState()
        self._event_log.clear()

    async def connect(
        self,
        player_id: str,
        *,
        nickname: str | None = None,
        skin: str | None = None,
    ) -> None:
        async with self._lock:
            player = self.world.players.get(player_id)
            if player is None:
                player = PlayerState(player_id=player_id)
                self.world.players[player_id] = player
            else:
                player.connected = True
            if nickname is not None:
                player.nickname = nickname
            if skin is not None:
                player.skin = skin

    async def update_identity(
        self,
        player_id: str,
        *,
        nickname: str | None = None,
        skin: str | None = None,
    ) -> None:
        async with self._lock:
            player = self.world.players.get(player_id)
            if player is None:
                return
            if nickname is not None:
                player.nickname = nickname
            if skin is not None:
                player.skin = skin

    async def disconnect(self, player_id: str) -> None:
        async with self._lock:
            player = self.world.players.get(player_id)
            if player is None:
                return
            player.connected = False
            player.move_x = 0.0
            player.move_y = 0.0
            if player.status == "queued":
                player.status = "roaming"

    async def join_queue(self, player_id: str) -> tuple[bool, str]:
        async with self._lock:
            return queue_player(self.world, player_id)

    async def leave_queue(self, player_id: str) -> tuple[bool, str]:
        async with self._lock:
            return leave_queue(self.world, player_id)

    async def forfeit(self, player_id: str) -> tuple[bool, str]:
        async with self._lock:
            return forfeit(self.world, player_id)

    async def perform(
        self,
        player_id: str,
        action: str,
        loot_id: str | None,
        item_id: str | None,
    ) -> tuple[bool, str]:
        async with self._lock:
            player = self.world.players.get(player_id)
            if player is None:
                return False, "Player is not connected"
            return apply_action(self.world, player, action, loot_id, item_id, self.rules)

    async def set_input(
        self,
        player_id: str,
        move_x: float,
        move_y: float,
        aim_x: float = 0.0,
        aim_y: float = 0.0,
    ) -> int:
        async with self._lock:
            player = self.world.players.setdefault(player_id, PlayerState(player_id=player_id))
            player.move_x = move_x
            player.move_y = move_y
            if aim_x or aim_y:
                player.aim_x = aim_x
                player.aim_y = aim_y
            player.connected = True
            return self.world.tick

    async def step(self, dt: float) -> list[dict]:
        async with self._lock:
            world = self.world
            world.tick += 1
            simulate(world, dt, self.rules)
            snapshots = [
                snapshot(world, player, self.rules)
                for player in world.players.values()
                if player.connected and not player.is_bot
            ]
            for match in world.matches.values():
                for event in match.events:
                    self._event_log.append({"tick": world.tick, "match_id": match.match_id, **event})
                match.events.clear()
            return snapshots

    async def take_results(self) -> list[MatchResult]:
        async with self._lock:
            results = list(self.world.pending_results)
            self.world.pending_results.clear()
            return results

    async def lobby_status(self) -> dict:
        async with self._lock:
            return lobby_view(self.world)

    async def list_matches(self) -> dict:
        async with self._lock:
            return matches_view(self.world)

    async def match_status(self, match_id: str) -> dict | None:
        async with self._lock:
            return match_view(self.world, match_id)


    async def spectate(self, match_id: str | None, since_tick: int, *, static: bool) -> dict:
        """Frames for one match (or every match when match_id is None) and events after since_tick."""
        async with self._lock:
            world = self.world
            if match_id is None:
                chosen = list(world.matches.values())
            else:
                match = world.matches.get(match_id)
                chosen = [match] if match is not None else []
            wanted = {match.match_id for match in chosen}
            events = [event for event in self._event_log if event["tick"] > since_tick and event["match_id"] in wanted]
            return {
                "tick": world.tick,
                "matches": [spectator_frame(world, match, self.rules, static=static) for match in chosen],
                "events": events[-EVENTS_PER_FRAME:],
                "found": match_id is None or bool(chosen),
            }


game_engine = GameEngine()

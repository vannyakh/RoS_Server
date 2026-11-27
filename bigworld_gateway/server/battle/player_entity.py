"""Shared in-match player runtime for humans and bots (gateway-local).

Durable account data lives in RoS_Server (`/api/v1/gateway`, SQL). This module holds
only match-scoped state: health, stance, battle inventory, and lifecycle. Depot /
cosmetic ownership is not copied into ``battle_inventory`` on match start.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import account_link

# Lifecycle (gateway convention; not original enum ids).
LIFECYCLE_MATCH_LOADING = "MATCH_LOADING"
LIFECYCLE_PREP = "PREPARATION"
LIFECYCLE_AIRCRAFT = "AIRCRAFT"
LIFECYCLE_PARACHUTE = "PARACHUTE"
LIFECYCLE_GROUND = "GROUND"
LIFECYCLE_VEHICLE = "VEHICLE"
LIFECYCLE_ELIMINATED = "ELIMINATED"
LIFECYCLE_SPECTATOR = "SPECTATOR"
LIFECYCLE_RESULTS = "RESULTS"

GROUND_LIFECYCLES = frozenset(
    {LIFECYCLE_PREP, LIFECYCLE_GROUND, LIFECYCLE_VEHICLE, LIFECYCLE_PARACHUTE}
)

STANCE_STANDING = "STANDING"
STANCE_CROUCH = "CROUCH"
STANCE_PRONE = "PRONE"

MOVEMENT_IDLE = "IDLE"
MOVEMENT_WALK = "WALK"
MOVEMENT_SPRINT = "SPRINT"
MOVEMENT_SWIM = "SWIM"

ACTION_NONE = "NONE"
ACTION_FIRE = "FIRE"
ACTION_RELOAD = "RELOAD"
ACTION_HEAL = "HEAL"
ACTION_INTERACT = "INTERACT"


@dataclass
class PlayerRuntimeState:
    """Authoritative gateway copy of one combatant during a match."""

    player_id: str
    match_id: str | None = None
    is_bot: bool = False
    entity_id: int | None = None
    nickname: str | None = None
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: float = 0.0
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    health: float = 100.0
    max_health: float = 100.0
    lifecycle: str = LIFECYCLE_MATCH_LOADING
    stance: str = STANCE_STANDING
    movement_state: str = MOVEMENT_IDLE
    action_state: str = ACTION_NONE
    active_weapon_slot: int | None = None
    vehicle_id: int | None = None
    appearance: dict[str, Any] = field(default_factory=dict)
    equipment: dict[str, Any] = field(default_factory=dict)
    battle_inventory: dict[str, int] = field(default_factory=dict)
    gun_slots: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    mags: dict[str, int] = field(default_factory=dict)
    kills: int = 0
    damage_dealt: float = 0.0
    survival_seconds: float = 0.0
    alive: bool = True
    connected: bool = True

    def reset_battle_loadout(self) -> None:
        """Clear match loot and weapons; keep ``appearance`` and identity."""
        self.battle_inventory.clear()
        self.gun_slots = {1: 0, 2: 0}
        self.mags.clear()
        self.equipment.clear()
        self.active_weapon_slot = None
        self.vehicle_id = None
        self.action_state = ACTION_NONE
        self.health = self.max_health
        self.alive = True
        self.kills = 0
        self.damage_dealt = 0.0
        self.survival_seconds = 0.0

    def can_perform_combat_action(self) -> bool:
        if not self.alive or not self.connected:
            return False
        if self.lifecycle in (LIFECYCLE_ELIMINATED, LIFECYCLE_RESULTS, LIFECYCLE_SPECTATOR):
            return False
        if self.action_state == ACTION_HEAL:
            return False
        return True

    def set_eliminated(self) -> None:
        self.alive = False
        self.health = 0.0
        self.lifecycle = LIFECYCLE_ELIMINATED
        self.action_state = ACTION_NONE
        self.active_weapon_slot = None
        self.vehicle_id = None

    def apply_damage(self, amount: float) -> float:
        if not self.alive or amount <= 0:
            return 0.0
        dealt = min(float(amount), self.health)
        self.health -= dealt
        if self.health <= 0:
            self.set_eliminated()
        return dealt

    def sync_position(self, x: float, y: float, z: float) -> None:
        self.position = (float(x), float(y), float(z))


def new_human_player(*, player_id: str | None = None, nickname: str | None = None) -> PlayerRuntimeState:
    """Build a fresh human combatant for a new MatchSession."""
    pid = player_id if player_id is not None else str(account_link.current_gid())
    if nickname is None:
        cur = account_link.current() or {}
        nickname = str(cur.get("nickname") or os.environ.get("BATTLE_NICK", "Player"))[:32]
    max_hp = float(os.environ.get("BATTLE_MAX_HP", "100"))
    state = PlayerRuntimeState(
        player_id=pid,
        nickname=nickname,
        is_bot=False,
        max_health=max_hp,
        health=max_hp,
        lifecycle=LIFECYCLE_MATCH_LOADING,
    )
    state.reset_battle_loadout()
    return state


def new_bot_player(
    *,
    player_id: str,
    entity_id: int,
    nickname: str,
    max_health: float = 100.0,
    position: tuple[float, float, float] | None = None,
) -> PlayerRuntimeState:
    """Build a bot combatant tied to a Robot entity id."""
    state = PlayerRuntimeState(
        player_id=str(player_id),
        entity_id=int(entity_id),
        nickname=str(nickname)[:32],
        is_bot=True,
        max_health=float(max_health),
        health=float(max_health),
        lifecycle=LIFECYCLE_PREP,
    )
    if position is not None:
        state.sync_position(*position)
    state.reset_battle_loadout()
    return state
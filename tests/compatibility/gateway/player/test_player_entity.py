"""Shared gateway PlayerRuntimeState (human + bot)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

GW = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GW) not in sys.path:
    sys.path.insert(0, str(GW))

from battle import player_entity as pe  # noqa: E402


def test_reset_battle_loadout_clears_weapons_keeps_appearance():
    p = pe.PlayerRuntimeState(player_id="1", appearance={"skin": "recruit"})
    p.gun_slots[1] = 10001
    p.battle_inventory["bandage"] = 2
    p.reset_battle_loadout()
    assert p.gun_slots == {1: 0, 2: 0}
    assert p.battle_inventory == {}
    assert p.appearance == {"skin": "recruit"}


def test_eliminated_blocks_combat():
    p = pe.PlayerRuntimeState(player_id="1")
    p.set_eliminated()
    assert not p.can_perform_combat_action()
    assert p.lifecycle == pe.LIFECYCLE_ELIMINATED


def test_apply_damage_eliminates_at_zero():
    p = pe.PlayerRuntimeState(player_id="1", health=10.0, max_health=100.0)
    p.apply_damage(10.0)
    assert not p.alive
    assert p.health == 0.0


def test_new_bot_player_registers_prep_lifecycle():
    bot = pe.new_bot_player(
        player_id="bot:40001",
        entity_id=40001,
        nickname="Bot01",
        position=(1.0, 2.0, 3.0),
    )
    assert bot.is_bot
    assert bot.lifecycle == pe.LIFECYCLE_PREP
    assert bot.position == (1.0, 2.0, 3.0)
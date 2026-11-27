"""Position msg 3 → PlayerRuntimeState / zone bridge."""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

GW = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GW) not in sys.path:
    sys.path.insert(0, str(GW))

from battle import player_entity as pe  # noqa: E402
from battle.position_sync import try_sync_xyz  # noqa: E402


class StubZone:
    def __init__(self):
        self.pos_x = 0.0
        self.pos_z = 0.0

    def track_position(self, x, z):
        self.pos_x = float(x)
        self.pos_z = float(z)


class StubSession:
    def __init__(self):
        self.player = pe.new_human_player()
        self.zone_module = StubZone()


def test_try_sync_xyz_short_payload():
    s = StubSession()
    assert try_sync_xyz(s, b"\x00" * 10) is None


def test_try_sync_xyz_updates_player_and_zone():
    s = StubSession()
    payload = b"\x00" * 8 + struct.pack("<3f", 100.0, 200.0, -300.0)
    out = try_sync_xyz(s, payload)
    assert out == (100.0, 200.0, -300.0)
    assert s.player.position == (100.0, 200.0, -300.0)
    assert s.zone_module.pos_x == 100.0
    assert s.zone_module.pos_z == -300.0
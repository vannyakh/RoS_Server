"""BattleGroundSpace create/remove via MatchSession module (RO-061).

Sources: battle_flow create_entity / leave_aoi / update_property (RO-059),
LOBBY_FINDINGS updates 14-15 (gameStatus PREPARE=1 HUD countdown; aliveNum 'N LEFT').
Gateway aliveNum/durations are not original RoS values.
"""

from __future__ import annotations

import pickle
import struct
from pathlib import Path

import bwdefs
from battle.session import MatchSession, load_battle_modules
from battle.timeline import MatchTimeline

from conftest import ADDR

MODULES_DIR = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server" / "battle" / "modules"


def _py(value):
    return bwdefs.blob(pickle.dumps(value, protocol=2))


def test_register_creates_space_with_required_props(session, sent, bf, space_mod):
    mod = space_mod.register(session)
    assert sent == [] and not mod.created          # nothing during the client's loading screen
    session.flow.enter("waiting")                  # client in the world -> waiting stage
    assert mod.created
    assert len(sent) == 1
    body = sent[0]
    expected = bf.create_entity(
        session.space_id,
        "BattleGroundSpace",
        values=space_mod.build_space_values(
            mod.defaults, stage_start=mod.stage_start, plane_id=session.plane_id
        ),
    )
    assert body == expected
    assert struct.unpack_from("<I", body, 1)[0] == 20001
    assert mod.defaults["mapID"] == 700
    assert mod.defaults["gameStatus"] == 1
    assert mod.defaults["aliveNum"] == 100
    assert mod.defaults["aliveNum"] != 120  # not the client default '120 LEFT'
    assert mod.defaults["weatherID"] == 0
    assert mod.defaults["gameStartTime"] == 0
    assert mod.defaults["clientStatus"] is None


def test_session_end_removes_space(session, sent, bf, space_mod):
    space_mod.register(session)
    session.flow.enter("waiting")
    assert len(sent) == 1
    session.close()
    assert len(sent) == 2
    assert sent[1] == bf.leave_aoi(20001)
    assert session.closed
    assert session.space_module.removed


def test_warmup_to_boarding_updates_game_status(session, sent, clock, bf, space_mod):
    tl = MatchTimeline({"warmup": 3.0, "boarding": 1.0, "flight": 1.0, "play": 0.0})
    mod = space_mod.SpaceModule(session, timeline=tl)
    mod.start()
    assert len(sent) == 1  # createEntity only
    clock.advance(0.0)  # enter warmup (delay 0); no property update yet
    assert len(sent) == 1
    clock.advance(3.0)  # boarding -> gameStatus BEFORE_FIGHT (2)
    assert len(sent) == 2
    assert sent[1] == bf.update_property(
        "BattleGroundSpace", "gameStatus", bf.i32(2), eid=20001
    )
    assert mod.defaults["gameStatus"] == 2


def test_auto_load_from_modules_dir(sent, clock):
    """load_battle_modules picks up space.py register()."""
    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    loaded = load_battle_modules(session, MODULES_DIR, log=lambda *_a, **_k: None)
    names = [Path(getattr(m, "__file__", "")).name for m in loaded]
    assert "space.py" in names
    assert sent == []                              # the match waits for the client
    session.start_match("test")
    clock.advance(0.0)
    assert len(sent) >= 1
    assert sent[0][:1] == b"\x0b"  # enterAoI


def test_build_space_values_uses_ro059_encoders(bf, space_mod):
    defaults = space_mod._load_space_defaults()
    values = space_mod.build_space_values(defaults, stage_start=1.0, plane_id=20002)
    assert values["mapID"] == bf.i32(700)
    assert values["gameStatus"] == bf.i32(1)
    assert values["aliveNum"] == bf.i32(100)
    assert values["weatherID"] == bf.i32(0)
    assert values["gameStartTime"] == bf.i32(0)
    assert values["clientStatus"] == _py(None)
    assert values["clientStatus"] == bwdefs.blob(bytes.fromhex("80024e2e"))
    msg = bf.create_entity(20001, "BattleGroundSpace", values=values)
    assert msg[:1] == b"\x0b"
    assert bf.leave_aoi(20001) == bytes.fromhex("0f0400214e0000")


def test_alive_num_env_override(monkeypatch, session, sent, space_mod):
    monkeypatch.setenv("SPACE_ALIVE_NUM", "42")
    mod = space_mod.SpaceModule(session)
    mod.start()
    assert mod.defaults["aliveNum"] == 42
    assert mod.defaults["aliveNum"] != 120

"""Plane create, boarding props, and inJumpArea timeline (RO-062).

Sources: battle_flow create_entity / leave_aoi / update_property (RO-059),
LOBBY_FINDINGS updates 8/9/15 (Plane type 147; planeID -> on-plane pose;
FlightStage Launch=0 Fly=1; inJumpArea jump prompt).
movePath and phase lengths are gateway parameters, not original RoS values.
"""

from __future__ import annotations

import struct
from pathlib import Path

from battle.session import MatchSession, load_battle_modules
from battle.timeline import MatchTimeline

from conftest import ADDR

MODULES_DIR = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server" / "battle" / "modules"


def _start_plane(plane_mod, session, timeline=None, **kwargs):
    """Synchronous start for unit tests (skips register's deferred schedule)."""
    mod = plane_mod.PlaneModule(session, timeline=timeline, **kwargs)
    mod.start()
    return mod


def test_build_plane_values_uses_ro059_encoders(bf, plane_mod):
    values = plane_mod.build_plane_values()
    assert values["mapID"] == bf.i32(700)
    assert values["moveSpeed"] == bf.f32(60.0)
    assert values["inJumpArea"] == bf.i8(0)
    assert values["mode"] == bf.i32(0)
    path = plane_mod.build_move_path()
    assert path == [(0.0, 300.0, 0.0), (2000.0, 300.0, 2000.0)]
    assert values["movePath"] == bf.arr_vec3(path)
    msg = bf.create_entity(20002, "Plane", values=values)
    assert msg[:1] == b"\x0b"
    assert struct.unpack_from("<I", msg, 1)[0] == 20002
    assert bf.client_type("Plane") == 147
    assert len(bf.other_client_props("Plane")) == 8


def test_boarding_creates_plane_and_player_props(session, sent, clock, bf, plane_mod):
    tl = MatchTimeline({"warmup": 3.0, "boarding": 2.0, "flight": 8.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl)
    assert len(sent) == 0

    clock.advance(0.0)  # warmup
    assert len(sent) == 0
    assert not mod.created

    clock.advance(3.0)  # boarding
    assert mod.created
    expected_create = bf.create_entity(
        session.plane_id,
        "Plane",
        values=plane_mod.build_plane_values(move_path=mod.move_path),
    )
    assert sent[0] == expected_create

    assert sent[1] == bf.update_property(
        "BattleGroundSpace", "getOnPlaneTime", bf.i32(3), eid=20001
    )
    assert sent[2] == bf.update_property(
        "BattleGroundSpace",
        "planeEntityIDs",
        bf.arr_i32([20002]),
        eid=20001,
    )
    assert sent[3] == bf.update_property(
        "BattleGroundAvatar", "planeID", bf.i32(20002)
    )
    assert sent[4] == bf.update_property(
        "BattleGroundAvatar", "flightStage", bf.i32(plane_mod.FLIGHT_STAGE_LAUNCH)
    )
    assert sent[5] == bf.update_property(
        "BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(1)
    )
    assert mod.plane_id_prop == 20002
    assert mod.flight_stage == plane_mod.FLIGHT_STAGE_LAUNCH
    assert mod.in_jump_area is False


def test_flight_sets_fly_stage_and_jump_window(session, sent, clock, bf, plane_mod):
    tl = MatchTimeline({"warmup": 1.0, "boarding": 1.0, "flight": 4.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl)
    clock.advance(1.0)  # boarding at t=1
    assert mod.created
    assert tl.phase == "boarding"
    boarding_count = len(sent)

    clock.advance(1.0)  # flight at t=2
    assert tl.phase == "flight"
    assert mod.flight_stage == plane_mod.FLIGHT_STAGE_FLY
    assert sent[boarding_count] == bf.update_property(
        "BattleGroundAvatar", "flightStage", bf.i32(plane_mod.FLIGHT_STAGE_FLY)
    )

    # jump window: 25%..75% of 4s flight => +1.0 .. +3.0 from flight enter
    pre = len(sent)
    clock.advance(1.0)
    assert mod.in_jump_area is True
    assert sent[pre] == bf.update_property(
        "Plane", "inJumpArea", bf.i8(1), eid=20002
    )

    clock.advance(2.0)
    assert mod.in_jump_area is False
    assert sent[-1] == bf.update_property(
        "Plane", "inJumpArea", bf.i8(0), eid=20002
    )


def test_session_end_removes_plane(session, sent, clock, bf, plane_mod):
    tl = MatchTimeline({"warmup": 0.0, "boarding": 1.0, "flight": 1.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl)
    clock.advance(0.0)  # warmup + immediate boarding (warmup 0)
    assert mod.created
    n = len(sent)
    session.close()
    assert len(sent) == n + 1
    assert sent[-1] == bf.leave_aoi(20002)
    assert mod.removed
    assert session.closed


def test_register_deferred_shares_space_timeline(sent, clock, plane_mod):
    """register() defers start; with space loaded first via manual attach, share timeline."""
    from battle.session import MatchSession

    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    tl = MatchTimeline({"warmup": 1.0, "boarding": 1.0, "flight": 2.0, "play": 0.0})

    class _SpaceShim:
        timeline = tl

    session.space_module = _SpaceShim()
    session.timeline = tl          # the session owns the match's one timeline (battle/flow.py)
    tl.start(session)
    mod = plane_mod.register(session)
    clock.advance(0.0)  # deferred plane start + warmup
    assert mod.timeline is tl
    assert mod._owns_timeline is False
    clock.advance(1.0)  # boarding
    assert mod.created


def test_auto_load_from_modules_dir(sent, clock):
    """load_battle_modules picks up plane.py register() (BATTLE_SPACE path unused here)."""
    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    loaded = load_battle_modules(session, MODULES_DIR, log=lambda *_a, **_k: None)
    names = [Path(getattr(m, "__file__", "")).name for m in loaded]
    assert "plane.py" in names
    assert "space.py" in names
    # plane defers; space creates immediately
    assert len(sent) >= 1
    assert sent[0][:1] == b"\x0b"  # space enterAoI
    clock.advance(0.0)  # plane deferred start (+ shared or own warmup)
    # Advance through warmup default 3s to boarding
    clock.advance(3.0)
    # Expect a Plane createEntity among sent bodies
    plane_creates = [
        b for b in sent
        if len(b) > 10 and b[:1] == b"\x0b" and struct.unpack_from("<I", b, 1)[0] == 20002
    ]
    assert len(plane_creates) >= 1


def test_left_on_plane_env_override(monkeypatch, session, sent, clock, bf, plane_mod):
    monkeypatch.setenv("PLANE_LEFT_PLAYER_NUM", "7")
    tl = MatchTimeline({"warmup": 0.0, "boarding": 1.0, "flight": 1.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl)
    clock.advance(0.0)
    assert mod.left_on_plane == 7
    assert any(
        b == bf.update_property(
            "BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(7)
        )
        for b in sent
    )

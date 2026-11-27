"""Jump window requests, force-drop and landing (RO-063).

Sources: battle.requests (RO-060) for decode/encode fixtures;
battle_flow update_property / forcedPosition (RO-059 / LOBBY_FINDINGS);
Plane.inJumpArea from RO-062. Gateway drop/land points and timers only —
not original Rules of Survival combat values.
"""

from __future__ import annotations

import struct
from pathlib import Path

from battle.session import MatchSession, load_battle_modules
from battle.timeline import MatchTimeline

from conftest import ADDR

MODULES_DIR = (
    Path(__file__).resolve().parents[4]
    / "bigworld_gateway"
    / "server"
    / "battle"
    / "modules"
)


class _PlaneShim:
    """Minimal plane_module stand-in for jump-window gating."""

    def __init__(self, in_jump_area=False, left_on_plane=1):
        self.in_jump_area = bool(in_jump_area)
        self.left_on_plane = int(left_on_plane)
        self.timeline = None


def _start_jump(jump_mod, session, timeline=None, plane=None, **kwargs):
    if plane is not None:
        session.plane_module = plane
    mod = jump_mod.JumpModule(session, timeline=timeline, own_timeline=True, **kwargs)
    mod.start()
    return mod


def _dispatch_frame(session, frame):
    msgid = frame[0]
    length = struct.unpack_from("<H", frame, 1)[0]
    payload = frame[3 : 3 + length]
    return session.dispatch_inbound(msgid, payload)


def test_forced_position_matches_battle_flow_tp(bf, jump_mod):
    body = jump_mod.forced_position(698.0, 19300.0, -373.0)
    expected = bf.debug_command("tp 698 19300 -373")
    assert body == expected
    assert body[:1] == bytes([0x59])
    assert len(body) == 37


def test_ignore_requests_outside_jump_window(session, sent, jump_mod, reqs):
    plane = _PlaneShim(in_jump_area=False)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 10.0, "play": 0.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    assert mod.in_jump_window() is False

    for name in ("requestGetOffPlane", "chooseParachute", "chooseGlider"):
        frame = reqs.encode_call("BattleGroundAvatar", name, 0)
        # requestGetOffPlane empty-args encode; capture may add ffffffff — both OK.
        assert _dispatch_frame(session, frame) == b""
        assert mod.off_plane is False
    assert sent == []


def test_request_get_off_plane_in_window_uses_ro060_fixture(
    session, sent, clock, bf, jump_mod, reqs, monkeypatch
):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    plane = _PlaneShim(in_jump_area=True, left_on_plane=1)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 10.0, "play": 0.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    clock.advance(0.0)

    # RO-060 capture form: payload with EXPOSED_SHIFT + length quirk args.
    payload = bytes.fromhex("0000000013ffffffff")
    assert _dispatch_frame(session, bytes([0xBC]) + struct.pack("<H", 9) + payload) == b""
    assert mod.off_plane is True
    assert plane.left_on_plane == 0

    assert sent[0] == bf.update_property("BattleGroundAvatar", "planeID", bf.i32(0))
    assert sent[1] == jump_mod.forced_position(*jump_mod.DEFAULT_DROP_POS)
    assert sent[2] == bf.update_property(
        "BattleGroundAvatar", "fallPhase", bf.i8(jump_mod.FALL_CAN_FALL)
    )
    assert sent[3] == bf.update_property(
        "BattleGroundAvatar", "battleState", bf.i8(jump_mod.BATTLE_STATE_PARACHUTE)
    )
    assert sent[4] == bf.update_property(
        "BattleGroundAvatar", "flightStage", bf.i32(jump_mod.FLIGHT_STAGE_FLY)
    )
    assert sent[5] == bf.update_property(
        "BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(0)
    )


def test_choose_parachute_and_glider_only_in_window(
    session, sent, clock, bf, jump_mod, reqs, monkeypatch
):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    plane = _PlaneShim(in_jump_area=True)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 10.0, "play": 0.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    clock.advance(0.0)

    para = reqs.encode_call("BattleGroundAvatar", "chooseParachute", 0)
    assert reqs.decode_frame(para).method == "chooseParachute"
    _dispatch_frame(session, para)
    assert mod.off_plane is True
    assert mod.choice == "parachute"
    assert any(
        b
        == bf.update_property(
            "BattleGroundAvatar",
            "fallPhase",
            bf.i8(jump_mod.FALL_PARACHUTE_OPENED),
        )
        for b in sent
    )

    # Outside window: glider ignored (new session state after clearing area).
    n = len(sent)
    plane.in_jump_area = False
    glider = reqs.encode_call("BattleGroundAvatar", "chooseGlider", 0)
    _dispatch_frame(session, glider)
    assert len(sent) == n
    assert mod.choice == "parachute"


def test_choose_glider_in_window(session, sent, clock, bf, jump_mod, reqs, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    plane = _PlaneShim(in_jump_area=True)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 10.0, "play": 0.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    clock.advance(0.0)

    glider = reqs.encode_call("BattleGroundAvatar", "chooseGlider", 0)
    assert reqs.decode_frame(glider).method == "chooseGlider"
    _dispatch_frame(session, glider)
    assert mod.choice == "glider"
    assert any(
        b
        == bf.update_property(
            "BattleGroundAvatar", "glidePhase", bf.i8(jump_mod.GLIDE_FREE)
        )
        for b in sent
    )
    assert any(
        b
        == bf.client_call(
            "BattleGroundAvatar", "onChangeToGliderAppear", bf.AVATAR_ID, b""
        )
        for b in sent
    )


def test_force_drop_when_never_jumps(session, sent, clock, bf, jump_mod, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    monkeypatch.setenv("PLANE_JUMP_END_FRAC", "0.5")
    plane = _PlaneShim(in_jump_area=False)
    # JumpModule schedules force at jump_end_frac * flight; flip inJumpArea like Plane.
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 4.0, "play": 1.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    clock.advance(0.0)  # flight enter + schedule
    assert mod.off_plane is False

    # Mid-flight jump window open (player still idle).
    plane.in_jump_area = True
    clock.advance(1.0)
    assert mod.off_plane is False

    # Window ends; force-drop fires at 0.5*4 + 0.01 = 2.01 from flight start.
    plane.in_jump_area = False
    clock.advance(1.02)
    assert mod.off_plane is True
    assert mod.force_dropped is True
    assert sent[0] == bf.update_property("BattleGroundAvatar", "planeID", bf.i32(0))
    assert any(b[:1] == bytes([0x59]) for b in sent)


def test_landing_after_delay(session, sent, clock, bf, jump_mod, reqs, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "2.0")
    plane = _PlaneShim(in_jump_area=True)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 20.0, "play": 0.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    clock.advance(0.0)

    frame = reqs.encode_call("BattleGroundAvatar", "requestGetOffPlane", 0)
    _dispatch_frame(session, frame)
    assert mod.off_plane is True
    assert mod.landed is False
    n = len(sent)

    clock.advance(2.0)
    assert mod.landed is True
    land_msgs = sent[n:]
    assert land_msgs[0] == jump_mod.forced_position(*jump_mod.DEFAULT_LAND_POS)
    assert land_msgs[1] == bf.update_property(
        "BattleGroundAvatar", "fallPhase", bf.i8(0)
    )
    assert land_msgs[2] == bf.update_property(
        "BattleGroundAvatar", "flightStage", bf.i32(jump_mod.FLIGHT_STAGE_GROUND)
    )
    assert land_msgs[3] == bf.update_property(
        "BattleGroundAvatar", "battleState", bf.i8(0)
    )


def test_register_deferred_with_plane_timeline(sent, clock, jump_mod, plane_mod, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 1.0, "flight": 4.0, "play": 0.0})
    plane = plane_mod.PlaneModule(session, timeline=tl, own_timeline=True)
    plane.start()
    jump = jump_mod.register(session)
    clock.advance(0.0)  # deferred jump start + boarding
    assert jump.timeline is tl
    assert jump._owns_timeline is False
    clock.advance(1.0)  # flight
    assert plane.flight_stage == plane_mod.FLIGHT_STAGE_FLY
    # Open jump window manually (plane schedules 25%..75%)
    clock.advance(1.0)
    assert plane.in_jump_area is True
    assert jump.in_jump_window() is True


def test_auto_load_jump_module(sent, clock):
    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    loaded = load_battle_modules(session, MODULES_DIR, log=lambda *_a, **_k: None)
    names = [Path(getattr(m, "__file__", "")).name for m in loaded]
    assert "jump.py" in names
    assert "plane.py" in names

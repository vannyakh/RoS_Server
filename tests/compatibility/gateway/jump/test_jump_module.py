"""Jump window requests, force-drop and landing (RO-063).

Sources: battle.requests (RO-060) for decode/encode fixtures;
battle_flow update_property / forcedPosition (RO-059 / LOBBY_FINDINGS);
Plane.inJumpArea from RO-062; LOBBY_FINDINGS update 25 (jump from the plane's position),
update 23 (fall phases by height, battle_flow.Match._parachute_phase), updates 22/25 (landing from
the client's position reports, battle_flow.Match.on_position); device run 3
(logs/checklist/run3/server.log: first report 22 s after the drop at y 19300, then a 46 s fall).
Fallback timers are gateway parameters, not original Rules of Survival values.
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


def test_request_get_off_plane_in_window(
    session, sent, clock, bf, jump_mod, reqs, monkeypatch
):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    plane = _PlaneShim(in_jump_area=True, left_on_plane=1)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 0.0, "flight": 10.0, "play": 0.0})
    mod = _start_jump(jump_mod, session, timeline=tl, plane=plane)
    clock.advance(0.0)

    # Encoded by the shared decoder rules (battle.requests), not a pinned sub-byte: the Jump button
    # is requestGetOffPlane (wire 77, below the exposed-index shift).
    frame = reqs.encode_call("BattleGroundAvatar", "requestGetOffPlane", 0)
    assert reqs.decode_frame(frame).method == "requestGetOffPlane"
    assert _dispatch_frame(session, frame) == b""
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


def test_timed_landing_only_without_position_reports(session, sent, clock, bf, jump_mod, reqs, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "2.0")
    monkeypatch.setenv("JUMP_NO_REPORT_LAND", "2.0")
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
    session.timeline = tl          # the session owns the match's one timeline (battle/flow.py)
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


# ---- plane position, passengers, fall and landing from the client's reports ---------------------

def _report(session, x, y, z):
    """One client position report through position_sync (msg-3 layout used by Match.on_position)."""
    from battle.position_sync import try_sync_xyz

    try_sync_xyz(session, struct.pack("<II3f", 1, 0, x, y, z) + b"\x00" * 12)


def _with_plane(jump_mod, plane_mod, session, *, flight=8.0, bots=0, seed=3, path=None):
    session.flow.set_slots(humans=1, bots=bots)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 2.0, "flight": flight, "play": 0.0})
    plane = plane_mod.PlaneModule(session, timeline=tl, own_timeline=True, seed=seed, move_path=path)
    plane.start()
    jump = jump_mod.JumpModule(session, timeline=tl, own_timeline=False)
    jump.start()
    session.player.sync_position(698.0, -677.0, -373.0)      # client in the world
    return plane, jump


def _forced(sent):
    return [struct.unpack_from("<3f", b, 13) for b in sent if b[:1] == bytes([0x59]) and len(b) == 37]


def _jump_now(session, reqs):
    _dispatch_frame(session, reqs.encode_call("BattleGroundAvatar", "requestGetOffPlane", 0))


def test_drop_point_is_the_plane_position_at_the_jump(session, sent, clock, bf, jump_mod, plane_mod, reqs):
    plane, jump = _with_plane(jump_mod, plane_mod, session)
    clock.advance(2.0 + 3.0)                                   # flight + 1 s: window open (25 % of 8 s)
    assert jump.in_jump_window()
    expected = plane.current_position()
    _jump_now(session, reqs)
    assert jump.off_plane and jump.jump_point == tuple(expected)
    fx, fy, fz = _forced(sent)[-1]
    assert (round(fx, 1), round(fy, 1), round(fz, 1)) == tuple(round(float(v), 1) for v in expected)
    assert fy == 19300.0
    assert expected != tuple(jump_mod.DEFAULT_DROP_POS)
    clock.advance(1.0)                                         # the plane moved on
    assert plane.current_position() != expected


def test_left_count_drops_as_bots_leave_and_the_human_jumps(session, sent, clock, bf, jump_mod, plane_mod, reqs):
    plane, jump = _with_plane(jump_mod, plane_mod, session, bots=9, seed=11)

    def left(n):
        return bf.update_property("BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(n))

    clock.advance(0.0)                                         # boarding: plane created
    assert plane.left_on_plane == 10
    clock.advance(2.0 + 4.0)                                   # flight + 4 s: middle of the window
    assert 0 < plane.bots_aboard < 9                           # some bots left, some still aboard
    before = plane.left_on_plane
    assert before == 1 + plane.bots_aboard
    assert left(before) in sent
    _jump_now(session, reqs)
    assert plane.left_on_plane == before - 1
    assert sent[-1] == left(before - 1) or left(before - 1) in sent
    assert plane.human_aboard is False
    clock.advance(4.0)                                         # window over: every bot has left
    assert plane.bots_aboard == 0 and plane.left_on_plane == 0
    assert len(plane.bot_drops) == 9
    assert left(0) in sent


def test_force_drop_at_window_end_from_the_plane(session, sent, clock, bf, jump_mod, plane_mod, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "100")
    plane, jump = _with_plane(jump_mod, plane_mod, session, bots=3)
    clock.advance(2.0 + 6.0 - 0.05)                            # just before the window end
    assert jump.off_plane is False
    clock.advance(0.1)
    assert jump.off_plane is True and jump.force_dropped is True
    assert session.flow.stage == "parachute"
    assert plane.left_on_plane == 0
    fx, fy, fz = _forced(sent)[-1]
    px, py, pz = jump.jump_point
    assert (round(fx), round(fy), round(fz)) == (round(px), round(py), round(pz))
    assert fy == 19300.0


def test_fall_phases_and_landing_follow_the_client_reports(session, sent, clock, bf, jump_mod, plane_mod, reqs):
    path = [(-20000.0, 19300.0, -373.0), (20000.0, 19300.0, -373.0)]
    plane, jump = _with_plane(jump_mod, plane_mod, session, path=path)
    clock.advance(2.0 + 3.0)
    _jump_now(session, reqs)
    n = len(sent)
    x, _y, z = jump.jump_point
    ground = jump_mod.FLIGHT_GROUND
    drop = 19300.0 - ground

    def fall(p):
        return bf.update_property("BattleGroundAvatar", "fallPhase", bf.i8(p))

    # a stale report from before the forcedPosition (old ground position) changes nothing
    _report(session, x, ground, z)
    clock.advance(0.2)
    assert jump.fall_started is False and fall(3) not in sent[n:]

    _report(session, x, 19300.0, z)
    clock.advance(0.2)
    assert jump.fall_started is True
    for frac, phase in ((0.03, 3), (0.61, 4), (0.96, 5)):
        _report(session, x, 19300.0 - drop * frac, z)
        clock.advance(0.2)
        assert jump.fall_phase == phase and fall(phase) in sent[n:]
    assert jump.landed is False
    # the timed landing (MatchFlow parachute recovery) is refused while the client is falling
    jump._land()
    assert jump.landed is False

    # on the ground: still for LAND_STILL_SECS -> landed where the client is, no teleport
    for _ in range(7):
        _report(session, x, ground, z)
        clock.advance(0.2)
    assert jump.landed is True and jump.landed_by == "position"
    assert session.flow.stage == "ground"
    tail = sent[n:]
    assert not any(b[:1] == bytes([0x59]) for b in tail)         # no forcedPosition after the jump
    i = tail.index(fall(0))
    assert tail[i:i + 4] == [
        fall(0),
        bf.update_property("BattleGroundAvatar", "flightStage", bf.i32(jump_mod.FLIGHT_STAGE_GROUND)),
        bf.update_property("BattleGroundAvatar", "battleState", bf.i8(0)),
        bf.update_property("BattleGroundAvatar", "hasLanded", bf.i8(1)),
    ]


def test_run3_late_reports_do_not_get_a_timed_landing(session, sent, clock, bf, jump_mod, plane_mod):
    """Device run 3: no report for 22 s after the drop, then a 46 s fall. The 8 s timed landing
    must not fire; the landing comes from the reports."""
    plane, jump = _with_plane(jump_mod, plane_mod, session)
    clock.advance(2.0 + 6.1)                                   # force-drop at the window end
    assert jump.off_plane and jump.force_dropped
    x, top, z = jump.jump_point
    clock.advance(22.0)                                        # loading screen: no reports
    assert jump.landed is False
    t, y = 0.0, top
    while y > jump_mod.FLIGHT_GROUND:                          # ~430 units/s, as measured
        _report(session, x, y, z)
        clock.advance(0.2)
        y -= 86.0
        t += 0.2
        assert jump.landed is False
    assert t > 40.0
    for _ in range(8):
        _report(session, x, jump_mod.FLIGHT_GROUND, z)
        clock.advance(0.2)
    assert jump.landed is True and jump.landed_by == "position"


def test_reports_that_stop_land_without_teleport(session, sent, clock, bf, jump_mod, plane_mod, reqs, monkeypatch):
    monkeypatch.setenv("JUMP_LAND_DELAY", "1.0")
    monkeypatch.setenv("JUMP_REPORT_STALE", "3.0")
    plane, jump = _with_plane(jump_mod, plane_mod, session)
    clock.advance(2.0 + 3.0)
    _jump_now(session, reqs)
    x, top, z = jump.jump_point
    n = len(sent)
    _report(session, x, top, z)
    clock.advance(0.2)
    _report(session, x, 5000.0, z)
    clock.advance(0.2)
    clock.advance(5.0)                                         # an idle client sends no more reports
    assert jump.landed is True and jump.landed_by == "fallback"
    assert not any(b[:1] == bytes([0x59]) for b in sent[n:])


def test_no_timed_landing_once_the_flow_is_on_the_ground(session, sent, clock, bf, jump_mod, plane_mod, reqs):
    """The legacy height landing may land the player first: no second landing, no teleport."""
    plane, jump = _with_plane(jump_mod, plane_mod, session)
    clock.advance(2.0 + 3.0)
    _jump_now(session, reqs)
    session.flow.enter("ground", "legacy landing")
    n = len(sent)
    jump._land(force=True)
    assert jump.landed is True and jump.landed_by == "flow"
    assert sent[n:] == []
    clock.advance(jump_mod.LAND_MAX + 1.0)
    assert not any(b[:1] == bytes([0x59]) for b in sent[n:])


def test_landing_bodies_go_before_the_ground_stage(session, sent, clock, bf, jump_mod, plane_mod, reqs):
    """Ground-stage listeners (zone FIGHT / circles) must follow the landing messages."""
    plane, jump = _with_plane(jump_mod, plane_mod, session)
    clock.advance(2.0 + 3.0)
    _jump_now(session, reqs)
    seen = []
    session.flow.on_enter("ground", lambda _s: seen.append(list(sent)))
    jump._land(force=True)
    before = seen[0]
    assert jump_mod.forced_position(*jump_mod.DEFAULT_LAND_POS) in before
    for name, value in (("fallPhase", bf.i8(0)), ("flightStage", bf.i32(2)), ("battleState", bf.i8(0))):
        assert bf.update_property("BattleGroundAvatar", name, value) in before

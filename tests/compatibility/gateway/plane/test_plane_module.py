"""Plane create, boarding props, and inJumpArea timeline (RO-062).

Sources: battle_flow create_entity / leave_aoi / update_property / detailed_position (RO-059),
LOBBY_FINDINGS updates 8/9/15 (Plane type 147; planeID -> on-plane pose;
FlightStage Launch=0 Fly=1; inJumpArea jump prompt), 21/22 (boarding: planeID 0 -> id,
leftPlayerNumOnPlane, fallPhase CAN_FALL a BOARD_DELAY after the plane, only once the client is in
the world), 25 (plane flown by detailedPosition 0x58 at 500 units/s, y 19300, mode 1), map 700
MAP_RANGE / CIRCLE_BOUND_BOX. Route randomness, start point on the route, jump-window fractions and
bot leave times are gateway parameters, not original RoS values.
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


DPOS = 0x58


def _no_dpos(bodies):
    """Drop the plane's detailedPosition stream (0x58) to check the other messages in order."""
    return [b for b in bodies if b[:1] != bytes([DPOS])]


def _dpos(bodies, eid=20002):
    """Decoded (x, y, z, yaw) of each detailedPosition for ``eid`` (battle_flow.detailed_position)."""
    out = []
    for b in bodies:
        if b[:1] == bytes([DPOS]) and len(b) == 31 and struct.unpack_from("<I", b, 1)[0] == eid:
            x, y, z, _r, _p, yaw = struct.unpack_from("<3f3f", b, 5)
            out.append((x, y, z, yaw))
    return out


def _in_world(session, x=698.0, y=-677.0, z=-373.0):
    session.player.sync_position(x, y, z)


def test_build_plane_values_uses_ro059_encoders(bf, plane_mod):
    path = [(-20000.0, 19300.0, 0.0), (20000.0, 19300.0, 100.0)]
    values = plane_mod.build_plane_values(move_path=path)
    assert values["mapID"] == bf.i32(700)
    assert values["moveSpeed"] == bf.f32(bf.FLIGHT_SPEED)       # 500, verified flight (update 25)
    assert values["inJumpArea"] == bf.i8(0)
    assert values["mode"] == bf.i32(1)                          # PEOPLE: the transport jet
    assert values["movePath"] == bf.arr_vec3(path)
    msg = bf.create_entity(20002, "Plane", values=values)
    assert msg[:1] == b"\x0b"
    assert struct.unpack_from("<I", msg, 1)[0] == 20002
    assert bf.client_type("Plane") == 147
    assert len(bf.other_client_props("Plane")) == 8


def test_route_crosses_the_play_area_edge_to_edge(plane_mod, bf):
    import math
    import random

    x0, z0, x1, z1 = plane_mod.MAP_RANGE
    bx0, bz0, bx1, bz1 = plane_mod.CIRCLE_BOUND_BOX
    opposite = {"west": "east", "east": "west", "south": "north", "north": "south"}
    seen_edges = set()

    def edge_of(x, z):
        if abs(x - x0) < 1e-3:
            return "west"
        if abs(x - x1) < 1e-3:
            return "east"
        if abs(z - z0) < 1e-3:
            return "south"
        if abs(z - z1) < 1e-3:
            return "north"
        return None

    for seed in range(200):
        route = plane_mod.generate_route(random.Random(seed))
        (sx, sy, sz), (ex, ey, ez) = route["path"]
        assert sy == ey == bf.FLIGHT_START[1] == 19300.0       # legacy drop height
        start_edge, end_edge = edge_of(sx, sz), edge_of(ex, ez)
        assert start_edge == route["edge"]
        assert end_edge == opposite[start_edge]                 # ends at the opposite edge
        seen_edges.add(start_edge)
        # the line passes over the play area: its aim point lies on it and inside the bound box
        ax, az = route["aim"]
        assert bx0 <= ax <= bx1 and bz0 <= az <= bz1
        cross = (ex - sx) * (az - sz) - (ez - sz) * (ax - sx)
        assert abs(cross) / math.hypot(ex - sx, ez - sz) < 1e-3
        assert math.hypot(ax - plane_mod.PLAY_CENTER[0], az - plane_mod.PLAY_CENTER[1]) <= plane_mod.ROUTE_SPREAD + 1e-6
    assert seen_edges == set(opposite)                          # every edge can be the entry


def test_boarding_creates_plane_and_boards_after_delay(session, sent, clock, bf, plane_mod):
    tl = MatchTimeline({"warmup": 3.0, "boarding": 2.0, "flight": 8.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl, seed=1)
    _in_world(session)
    assert len(sent) == 0

    clock.advance(0.0)  # warmup
    assert len(sent) == 0
    assert not mod.created

    clock.advance(3.0)  # boarding
    assert mod.created
    pos, yaw = mod.position_at(3.0)
    expected_create = bf.create_entity(
        session.plane_id,
        "Plane",
        pos=pos,
        direction=(0.0, 0.0, yaw),
        values=plane_mod.build_plane_values(move_path=mod.move_path),
    )
    msgs = _no_dpos(sent)
    assert msgs[0] == expected_create
    assert msgs[1] == bf.update_property(
        "BattleGroundSpace", "getOnPlaneTime", bf.i32(3), eid=20001
    )
    assert msgs[2] == bf.update_property(
        "BattleGroundSpace",
        "planeEntityIDs",
        bf.arr_i32([20002]),
        eid=20001,
    )
    assert msgs[3] == bf.update_property(
        "BattleGroundAvatar", "flightStage", bf.i32(plane_mod.FLIGHT_STAGE_LAUNCH)
    )
    assert len(msgs) == 4                     # planeID waits for the loaded plane (update 22)
    assert mod.boarded is False

    clock.advance(bf.BOARD_DELAY)
    msgs = _no_dpos(sent)[4:]
    flight_fly = bf.update_property("BattleGroundAvatar", "flightStage", bf.i32(plane_mod.FLIGHT_STAGE_FLY))
    msgs = [m for m in msgs if m != flight_fly]
    assert msgs[:4] == [
        bf.update_property("BattleGroundAvatar", "planeID", bf.i32(0)),
        bf.update_property("BattleGroundAvatar", "planeID", bf.i32(20002)),
        bf.update_property("BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(1)),
        bf.update_property("BattleGroundAvatar", "fallPhase", bf.i8(2)),
    ]
    assert mod.boarded is True and mod.plane_id_prop == 20002
    assert mod.in_jump_area is False


def test_no_planeid_while_the_client_is_still_loading(session, sent, clock, bf, plane_mod):
    """Device run 3: the aircraft stage ran under the loading screen. planeID is held until the
    client reports a position in the world (LOBBY_FINDINGS update 21)."""
    tl = MatchTimeline({"warmup": 0.0, "boarding": 2.0, "flight": 30.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl, seed=2)
    board = bf.update_property("BattleGroundAvatar", "planeID", bf.i32(20002))
    clock.advance(10.0)
    assert mod.created and board not in sent
    _in_world(session)
    clock.advance(0.2)
    assert sent.count(board) == 1
    # still on the ground in a later report: planeID again after BOARD_RETRY (update 21)
    _in_world(session, 698.0, -677.0, -372.0)
    clock.advance(plane_mod.BOARD_RETRY)
    assert sent.count(board) == 2
    # on the plane (reports at plane height): no more re-sends
    _in_world(session, 0.0, 19300.0, 0.0)
    clock.advance(plane_mod.BOARD_RETRY * 2)
    assert sent.count(board) == 2


def test_plane_flies_along_its_route(session, sent, clock, bf, plane_mod):
    import math

    path = [(-20000.0, 19300.0, -4000.0), (20000.0, 19300.0, -4000.0)]
    tl = MatchTimeline({"warmup": 0.0, "boarding": 2.0, "flight": 8.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl, move_path=path)
    clock.advance(0.0)
    start_arc = mod.start_arc
    clock.advance(4.0)
    track = _dpos(sent)
    assert len(track) >= 20                                       # every FLIGHT_POS_EVERY (0.2 s)
    xs = [p[0] for p in track]
    assert all(b > a for a, b in zip(xs, xs[1:]))                 # moving forward along x
    assert all(p[1] == 19300.0 and p[2] == -4000.0 for p in track)
    assert all(abs(p[3] - math.atan2(1.0, 0.0)) < 1e-6 for p in track)   # yaw along the route
    step = xs[1] - xs[0]
    assert abs(step - bf.FLIGHT_SPEED * bf.FLIGHT_POS_EVERY) < 1e-2   # 500 units/s
    assert abs(xs[0] - (path[0][0] + start_arc)) < 1e-3
    # mid jump window (boarding + 50 % of flight = 6 s) the plane is over the play-area centre
    clock.advance(2.0)
    x, _y, _z = mod.current_position()
    assert abs(x - plane_mod.PLAY_CENTER[0]) < 1.0


def test_plane_starts_at_the_edge_when_the_flight_is_long_enough(session, sent, clock, plane_mod, bf):
    path = [(-20000.0, 19300.0, 0.0), (20000.0, 19300.0, 0.0)]
    tl = MatchTimeline({"warmup": 0.0, "boarding": 2.0, "flight": 200.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl, move_path=path)
    clock.advance(0.0)
    assert mod.start_arc == 0.0
    assert _dpos(sent)[0][:3] == (-20000.0, 19300.0, 0.0)
    clock.advance(40000.0 / bf.FLIGHT_SPEED + 1.0)              # whole route
    assert mod.arrived is True
    assert _dpos(sent)[-1][:3] == (20000.0, 19300.0, 0.0)       # ends at the opposite edge
    n = len(sent)
    clock.advance(5.0)
    assert len(_dpos(sent[n:])) == 0                             # no more positions after the end


def test_flight_sets_fly_stage_and_jump_window(session, sent, clock, bf, plane_mod):
    tl = MatchTimeline({"warmup": 1.0, "boarding": 1.0, "flight": 4.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl)
    clock.advance(1.0)  # boarding at t=1
    assert mod.created
    assert tl.phase == "boarding"
    boarding_count = len(_no_dpos(sent))

    clock.advance(1.0)  # flight at t=2
    assert tl.phase == "flight"
    assert mod.flight_stage == plane_mod.FLIGHT_STAGE_FLY
    assert _no_dpos(sent)[boarding_count] == bf.update_property(
        "BattleGroundAvatar", "flightStage", bf.i32(plane_mod.FLIGHT_STAGE_FLY)
    )

    # jump window: 25%..75% of 4s flight => +1.0 .. +3.0 from flight enter
    pre = len(_no_dpos(sent))
    clock.advance(1.0)
    assert mod.in_jump_area is True
    assert _no_dpos(sent)[pre] == bf.update_property(
        "Plane", "inJumpArea", bf.i8(1), eid=20002
    )

    clock.advance(2.0)
    assert mod.in_jump_area is False
    assert _no_dpos(sent)[-1] == bf.update_property(
        "Plane", "inJumpArea", bf.i8(0), eid=20002
    )


def test_bots_leave_inside_the_window_and_count_down(session, sent, clock, bf, plane_mod, monkeypatch):
    monkeypatch.setenv("PLANE_BOARD_DELAY", "0.5")             # board before the window opens
    session.flow.set_slots(humans=1, bots=5)
    tl = MatchTimeline({"warmup": 0.0, "boarding": 1.0, "flight": 8.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl, seed=7)
    _in_world(session)
    clock.advance(0.0)
    assert mod.left_on_plane == 6 and mod.bots_aboard == 5

    def counts():
        return [
            struct.unpack_from("<i", b, len(b) - 4)[0]
            for b in sent
            if b[:-4] == bf.update_property("BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(0))[:-4]
        ]

    clock.advance(1.0 + 2.0 - 0.01)                            # just before the window opens
    assert mod.bots_aboard == 5 and counts() == [6]            # boarding sent the full plane
    clock.advance(4.0 + 0.02)                                  # through the window end
    assert mod.bots_aboard == 0 and mod.left_on_plane == 1     # only the human is left
    assert counts() == [6, 5, 4, 3, 2, 1]
    window = (1.0 + 2.0, 1.0 + 6.0)
    assert all(window[0] <= at < window[1] for at, _pos in mod.bot_drops)
    assert all(pos is not None and pos[1] == 19300.0 for _at, pos in mod.bot_drops)
    assert mod.human_left() == 0
    assert counts()[-1] == 0
    assert mod.human_left() == 0 and counts().count(0) == 1    # once


def test_exactly_one_plane_create_per_match(sent, clock, bf, plane_mod):
    from battle.position_sync import try_sync_xyz

    session = MatchSession(ADDR, lambda body: sent.append(body), clock=clock)
    load_battle_modules(session, MODULES_DIR, log=lambda *_a, **_k: None)
    report = struct.pack("<II3f", 1, 0, 698.0, -677.0, -373.0) + b"\x00" * 12
    try_sync_xyz(session, report)
    clock.advance(0.0)
    d = session.timeline.durations
    clock.advance(d["warmup"] + d["boarding"] + d["flight"] + 30.0)
    creates = [
        b for b in sent
        if b[:1] == b"\x0b" and len(b) > 10 and struct.unpack_from("<I", b, 1)[0] == 20002
    ]
    assert len(creates) == 1
    assert session.flow.reached("parachute")                   # force-dropped at the window end


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
    # Nothing until the match starts; then the space is created with the waiting stage.
    assert sent == []
    session.start_match("test")
    clock.advance(0.0)
    assert sent[0][:1] == b"\x0b"  # space enterAoI
    # Advance through the waiting stage to boarding
    clock.advance(session.timeline.durations["warmup"])
    # Expect a Plane createEntity among sent bodies
    plane_creates = [
        b for b in sent
        if len(b) > 10 and b[:1] == b"\x0b" and struct.unpack_from("<I", b, 1)[0] == 20002
    ]
    assert len(plane_creates) >= 1


def test_left_on_plane_env_override(monkeypatch, session, sent, clock, bf, plane_mod):
    monkeypatch.setenv("PLANE_LEFT_PLAYER_NUM", "7")
    monkeypatch.setenv("PLANE_BOARD_DELAY", "0")
    tl = MatchTimeline({"warmup": 0.0, "boarding": 1.0, "flight": 1.0, "play": 0.0})
    mod = _start_plane(plane_mod, session, timeline=tl)
    _in_world(session)
    clock.advance(0.0)
    assert mod.left_on_plane == 7
    assert any(
        b == bf.update_property(
            "BattleGroundAvatar", "leftPlayerNumOnPlane", bf.i32(7)
        )
        for b in sent
    )

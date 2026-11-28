"""Match results (server/match_results.py + battle_flow.Match.finish), parachute phases
(battle_flow.Match._parachute_phase via on_position), battle world vehicles / supply drop
(server/battle_world.py via the battle_flow hooks) and match rooms (server/match_room.py).

Entry points are driven the way ros_server's in-battle loop drives them: client cell calls go to
battle.session.MatchSession.dispatch_inbound first (None = not handled by a module) and then to
battle_flow.Match.handle; every message also goes to battle_flow.Match.on_message.
Method tables come from the extract entity defs (battle_flow.exposed_cell / client_methods)."""

import json
import struct

import pytest

from lobby_new_helpers import blob, encode_cell_request

A, B = ("10.0.0.7", 5007), ("10.0.0.8", 5008)


@pytest.fixture
def bf():
    import battle_flow
    return battle_flow


@pytest.fixture
def bw(bf):
    import battle_world
    return battle_world


@pytest.fixture
def match(bf):
    m = bf.Match()
    m.pos = (100.0, -400.0, 100.0)
    return m


def quiet(*_a, **_k):
    pass


def u32(v):
    return struct.pack("<I", v)


# ---- match results ---------------------------------------------------------------------------

def test_match_results_save_and_history(bf, tmp_path):
    import match_results as mr
    assert mr.PATH == str(tmp_path / "match_results.jsonl")
    m = bf.Match()
    m.t_start -= 95
    m.kills, m.collected = 3, 7
    rec = mr.save(m, 42, "Ann", 1, 100, won=True, log=quiet)
    assert rec["survival_s"] >= 95 and rec["cause"] == "win" and rec["kills"] == 3 and rec["collected"] == 7
    m2 = bf.Match()
    m2.death_cause = "zone"
    mr.save(m2, 43, "Bob", 57, 100, won=False, log=quiet)
    assert [r["gid"] for r in mr.history()] == [42, 43]
    assert [r["rank"] for r in mr.history(43)] == [57] and mr.history(43)[0]["cause"] == "zone"
    lines = (tmp_path / "match_results.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["nickname"] for x in lines] == ["Ann", "Bob"]


def test_match_results_history_skips_bad_lines(tmp_path):
    import match_results as mr
    (tmp_path / "match_results.jsonl").write_text('{"gid": 1}\nnot json\n{"gid": 2}\n', encoding="utf-8")
    assert [r["gid"] for r in mr.history()] == [1, 2]


def test_match_finish_saves_once_and_sends_the_result(bf, monkeypatch):
    import account_link
    import match_results as mr
    monkeypatch.delenv("TEST_ACCOUNT_NAME", raising=False)
    m = bf.Match()
    m.hp = 50
    gid = account_link.current_gid()
    out = m.finish(1, log=quiet)
    assert out == bf.result_call(1, bf.RESULT_TOTAL, gid, "Player", collected=0)   # 19.06 victory
    assert m.finish(1, log=quiet) == b""
    assert len(mr.history()) == 1 and mr.history()[0]["won"] is True


def test_match_finish_after_death_sends_die_then_result(bf, monkeypatch):
    import account_link
    monkeypatch.delenv("TEST_ACCOUNT_NAME", raising=False)
    m = bf.Match()
    m.hp = 0
    out = m.finish(bf.RESULT_TOTAL, log=quiet)                                       # 19.07 defeat
    gid = account_link.current_gid()
    assert out == bf.die_call() + bf.result_call(bf.RESULT_TOTAL, bf.RESULT_TOTAL, gid, "Player", collected=0)


def test_surviving_the_last_circle_wins_once(bf, monkeypatch):
    """14.15: battle_flow.Match._zone_shrink calls finish(1) when the last stage closes with hp > 0."""
    import account_link
    import match_results as mr
    monkeypatch.delenv("TEST_ACCOUNT_NAME", raising=False)
    m = bf.Match()
    (cx, cz), _r = bf.ZONE_INIT
    m.pos = (cx, 0.0, cz)                                        # stays inside every circle
    now = 0.0
    out = m.zone_start(now, scale=0.001, log=quiet)
    for _ in range(2000):
        now += 1.0
        out += m.zone_tick(now, log=quiet)
        if m.zone.get("done"):
            break
    assert m.zone.get("done") and m.hp == bf.MAX_HP
    win = bf.result_call(1, bf.RESULT_TOTAL, account_link.current_gid(), "Player", collected=0)
    assert out.endswith(win) and out.count(win) == 1
    assert [r["won"] for r in mr.history()] == [True]


# ---- parachute phases (battle_flow) -----------------------------------------------------------

def _pos(x, y, z):
    return b"\x00" * 8 + struct.pack("<3f", x, y, z)


def test_parachute_phases_follow_the_drop(bf, monkeypatch):
    monkeypatch.setenv("FLIGHT_GROUND", "-677")
    m = bf.Match()
    top, ground = 3000.0, -677.0
    drop = top - ground
    release = m.release_from_plane((0.0, top, 0.0), log=quiet)
    assert bf.prop_update("BattleGroundAvatar", bf.AVATAR_ID, "fallPhase", bf.i8(bf.FALL_CAN)) in release
    fp = lambda ph: bf.prop_update("BattleGroundAvatar", bf.AVATAR_ID, "fallPhase", bf.i8(ph))
    at = lambda frac: m.on_position(_pos(0, top - frac * drop, 0), 0.0, log=quiet)
    assert at(0.0) == b""                                        # near the jump point: start, no change
    assert at(0.1) == (bf.prop_update("BattleGroundAvatar", bf.AVATAR_ID, "battleState", bf.i8(bf.STATE_PARACHUTE))
                       + fp(bf.FALL_BEFORE_OPEN))
    assert at(0.3) == b""
    assert at(0.7) == fp(bf.FALL_CAN_OPEN)                       # parachute button
    assert at(0.96) == fp(bf.FALL_OPENED) and m.chute_open       # late automatic opening
    assert at(0.98) == b""


def test_parachute_client_mode_leaves_the_button_to_the_client(bf, monkeypatch):
    monkeypatch.setenv("CHUTE_MODE", "client")
    m = bf.Match()
    m.release_from_plane((0.0, 3000.0, 0.0), log=quiet)
    m.on_position(_pos(0, 3000.0, 0), 0.0, log=quiet)
    m.on_position(_pos(0, 2600.0, 0), 0.0, log=quiet)
    assert m.fall_phase == bf.FALL_BEFORE_OPEN
    assert m.on_position(_pos(0, -600.0, 0), 0.0, log=quiet) == b""
    assert m.fall_phase == bf.FALL_BEFORE_OPEN


# ---- battle world: entity ids and decode ------------------------------------------------------

def test_world_entity_ids_map_to_client_types(bf, bw):
    assert bf.entity_type_of(bw.VEHICLE_BASE) == "LandCar"
    assert bf.entity_type_of(bw.CRATE_BASE) == "DtsPlayerHeritage"
    assert bf.entity_type_of(bw.AIRDROP_PLANE_ID) == "Plane"
    assert bf.entity_type_of(26999) == "BattleGroundAvatar"


@pytest.mark.parametrize("method,args", [
    ("reqGetOnLandVehicleAsDriver", u32(26000)),
    ("reqGetOnLandVehicleAsPassenger", u32(26000)),
    ("reqGetOffLandVehicle", u32(26000)),
    ("reqSwitchToSeat", struct.pack("<i", 1)),
    ("reqSwitchToDriveLandVehicle", u32(26000)),
])
def test_vehicle_requests_decode_by_name(bf, method, args):
    msgid, payload = encode_cell_request(bf, bf.AVATAR_ID, "BattleGroundAvatar", method, args)
    assert bf.decode_request(msgid, payload) == (bf.AVATAR_ID, "BattleGroundAvatar", method, args)


def test_crate_pickup_decodes_on_dts_player_heritage(bf, bw):
    args = blob(b"\x01" * 16) + struct.pack("<ib", 0, 1)
    msgid, payload = encode_cell_request(bf, bw.CRATE_BASE, "DtsPlayerHeritage", "tryPickUp", args)
    assert bf.decode_request(msgid, payload) == (bw.CRATE_BASE, "DtsPlayerHeritage", "tryPickUp", args)


def test_world_requests_are_not_swallowed_by_session_modules(bf, bw):
    """ros_server runs MatchSession.dispatch_inbound first; None lets battle_flow (and so
    battle_world) answer. Checked with every production battle/modules module loaded."""
    from battle.session import MatchSession, load_battle_modules
    session = MatchSession(A, lambda body: None, log=quiet)
    load_battle_modules(session, log=quiet)
    assert session.modules
    for method, args in (("reqGetOnLandVehicleAsDriver", u32(26000)), ("reqGetOffLandVehicle", u32(26000)),
                         ("reqSwitchToSeat", struct.pack("<i", 0))):
        msgid, payload = encode_cell_request(bf, bf.AVATAR_ID, "BattleGroundAvatar", method, args)
        assert session.dispatch_inbound(msgid, payload) is None, method
    msgid, payload = encode_cell_request(bf, bw.CRATE_BASE, "DtsPlayerHeritage", "tryPickUp",
                                         blob(b"\x01" * 16) + struct.pack("<ib", 0, 1))
    assert session.dispatch_inbound(msgid, payload) is None


# ---- battle world: vehicles -------------------------------------------------------------------

def _call(bf, match, method, args, eid=None, entity="BattleGroundAvatar"):
    msgid, payload = encode_cell_request(bf, bf.AVATAR_ID if eid is None else eid, entity, method, args)
    return match.handle(msgid, payload, log=quiet)


def test_spawn_vehicle_creates_a_land_car(bf, bw, match):
    out = bw.spawn_vehicle(match, (1.0, 2.0, 3.0), log=quiet)
    vid = bw.VEHICLE_BASE
    assert out.startswith(bf.enter_aoi(vid))
    v = bw.state(match)["vehicles"][vid]
    assert v["pos"] == (1.0, 2.0, 3.0) and v["driver"] == 0 and v["seats"] == []
    assert bw.state(match)["next_vehicle"] == vid + 1


def test_driver_get_on_and_off(bf, bw, match):
    me = bf.AVATAR_ID
    bw.spawn_vehicle(match, (10.0, 0.0, 10.0), log=quiet)
    vid = bw.VEHICLE_BASE
    out = _call(bf, match, "reqGetOnLandVehicleAsDriver", u32(vid))
    v = bw.state(match)["vehicles"][vid]
    assert v["driver"] == me and v["seats"] == [(bw.DRIVER_SOCKET, me)]
    assert bw.control_entity(vid, True) in out
    assert bf.client_call("LandCar", "onAddAvatarSocket", vid, bw.string(bw.DRIVER_SOCKET) + u32(me)) in out
    assert bf.client_call("LandCar", "onControlledBy", vid, u32(me) + bw.b8(1)) in out
    assert bf.prop_update("BattleGroundAvatar", me, "vehicleEntID", u32(vid)) in out
    assert bf.prop_update("BattleGroundAvatar", me, "isLandDriver", bw.b8(1)) in out
    assert _call(bf, match, "reqGetOnLandVehicleAsPassenger", u32(vid)) == b""     # already seated

    off = _call(bf, match, "reqGetOffLandVehicle", u32(vid))
    assert v["driver"] == 0 and v["seats"] == [] and bw.state(match)["seat"] is None
    assert bw.control_entity(vid, False) in off
    assert bf.prop_update("BattleGroundAvatar", me, "vehicleEntID", u32(0)) in off
    assert bf.forced_position(me, (10.0 + 25.0, 5.0, 10.0)) in off                 # beside the car (yaw 0)
    assert _call(bf, match, "reqGetOffLandVehicle", u32(vid)) == b""


def test_passenger_seat_and_switch_to_driver(bf, bw, match):
    me = bf.AVATAR_ID
    bw.spawn_vehicle(match, (0.0, 0.0, 0.0), log=quiet)
    vid = bw.VEHICLE_BASE
    out = _call(bf, match, "reqGetOnLandVehicleAsPassenger", u32(vid))
    v = bw.state(match)["vehicles"][vid]
    assert v["seats"] == [(bw.PASSENGER_SOCKETS[0], me)] and v["driver"] == 0
    assert bw.control_entity(vid, True) not in out
    sw = _call(bf, match, "reqSwitchToSeat", struct.pack("<i", 0))
    assert v["seats"] == [(bw.DRIVER_SOCKET, me)] and v["driver"] == me
    assert bw.control_entity(vid, True) in sw
    assert bf.forced_position(me, (25.0, 5.0, 0.0)) not in sw                     # no teleport on a switch


def test_unknown_vehicle_and_unknown_request(bf, bw, match):
    assert _call(bf, match, "reqGetOnLandVehicleAsDriver", u32(26050)) == b""
    assert bw.handle(match, 1, "BattleGroundAvatar", "changePose", b"\x00", log=quiet) is None


def test_vehicle_position_report_is_tracked(bf, bw, match):
    bw.spawn_vehicle(match, (0.0, 0.0, 0.0), log=quiet)
    vid = bw.VEHICLE_BASE
    payload = u32(vid) + b"\x00" * 4 + struct.pack("<3ff", 5.0, 6.0, 7.0, 1.5)
    match.on_message(bw.MSG_AVATAR_UPDATE_EXPLICIT, payload, log=quiet)            # through the battle_flow hook
    v = bw.state(match)["vehicles"][vid]
    assert v["pos"] == (5.0, 6.0, 7.0) and v["yaw"] == 1.5 and v["moves"] == 1


def test_vehicle_spawns_after_landing_only_when_enabled(bf, bw, match, monkeypatch):
    match.stage, match.stage_time = "landed", 0.0
    assert bw.on_message(match, 99, b"", log=quiet) == b""                         # WORLD_VEHICLES off
    monkeypatch.setattr(bw, "VEHICLES", True)
    out = bw.on_message(match, 99, b"", log=quiet)
    assert out.startswith(bf.enter_aoi(bw.VEHICLE_BASE))
    assert bw.on_message(match, 99, b"", log=quiet) == b""                         # one car per match


# ---- battle world: supply drop ----------------------------------------------------------------

def test_airdrop_timeline_release_descent_and_landing(bf, bw, match):
    t0 = 1000.0
    out = bw.airdrop_start(match, t0, log=quiet)
    assert out.startswith(bf.enter_aoi(bw.AIRDROP_PLANE_ID))
    route = 2 * bw.AIRDROP_HALF / bw.AIRDROP_SPEED                                  # s to fly the route
    early = bw.airdrop_tick(match, t0 + route * 0.25, log=quiet)
    assert bw.airdrop_tick(match, t0 + route * 0.25 + 0.05, log=quiet) == b""      # POS_EVERY throttle
    assert early.startswith(b"\x58") and bw.state(match)["crates"] == {}            # detailedPosition only
    rel = bw.airdrop_tick(match, t0 + route * 0.55, log=quiet)
    cid = bw.CRATE_BASE
    assert bf.enter_aoi(cid) in rel and cid in bw.state(match)["crates"]
    gone = bw.airdrop_tick(match, t0 + route * 1.02, log=quiet)
    assert bf.leave_aoi(bw.AIRDROP_PLANE_ID) in gone
    fall = bw.AIRDROP_PLANE_HEIGHT / bw.AIRDROP_FALL_SPEED
    landed = bw.airdrop_tick(match, t0 + route * 0.55 + fall + 1, log=quiet)
    crate = bw.state(match)["crates"][cid]
    assert crate["landed"] and crate["pos"][1] == match.pos[1]
    assert bf.prop_update("DtsPlayerHeritage", cid, "dropping", bw.b8(0)) in landed
    assert bw.state(match)["airdrop"]["done"]
    assert bw.airdrop_tick(match, t0 + 999, log=quiet) == b""


def _crate(bw, match):
    bw._release_crate(match, (0.0, 0.0, 0.0), quiet)
    cid = bw.CRATE_BASE
    return cid, bw.state(match)["crates"][cid]


def test_crate_pickup_takes_the_item_once(bf, bw, match):
    cid, crate = _crate(bw, match)
    uuid, (pid, amount) = next(iter(crate["items"].items()))
    n_items = len(crate["items"])
    args = blob(uuid) + struct.pack("<ib", 0, 1)
    out = _call(bf, match, "tryPickUp", args, eid=cid, entity="DtsPlayerHeritage")
    assert uuid not in crate["items"] and len(crate["items"]) == n_items - 1
    assert match.collected == 1 and crate["opened"]
    assert bf.client_call("DtsPlayerHeritage", "resetItems", cid) in out
    assert bf.client_call("BattleGroundAvatar", "onPickUpPropEntity", bf.AVATAR_ID) in out
    assert struct.pack("<i", pid) + struct.pack("<I", 1) + blob(uuid) + struct.pack("<i", amount) in out
    assert _call(bf, match, "tryPickUp", args, eid=cid, entity="DtsPlayerHeritage") == b""   # gone
    assert match.collected == 1


def test_crate_partial_pickup_leaves_the_rest(bf, bw, match):
    cid, crate = _crate(bw, match)
    uuid, (pid, amount) = next((u, it) for u, it in crate["items"].items() if it[1] > 1)
    _call(bf, match, "tryPickUp", blob(uuid) + struct.pack("<ib", 1, 1), eid=cid, entity="DtsPlayerHeritage")
    assert crate["items"][uuid] == (pid, amount - 1)


def test_crate_items_pickle_round_trips_with_only_the_bytes_helper_global(bw):
    """The items PY_DICT is pickle protocol 2 built on Python 3: bytes uuid keys are written as
    _codecs.encode(u'...', 'latin1') (the only global). The Python 2 client must accept that."""
    import pickle
    import pickletools
    data = bw.crate_items({b"\x00" * 16: (1003, 1)})
    raw = data[1:] if data[0] != 0xFF else data[4:]
    assert pickle.loads(raw) == {b"\x00" * 16: {"itemID": 1003, "id": 1003, "propID": 1003, "amount": 1}}
    globals_used = {arg for op, arg, _pos in pickletools.genops(raw) if op.name == "GLOBAL"}
    assert globals_used == {"_codecs encode"}


# ---- match room ------------------------------------------------------------------------------

class FakeGate:
    def __init__(self, bf):
        self._last_bf = {A: b"\x01" * 16, B: b"\x02" * 16}
        self._last_client_seq = {}
        self._matches = {}
        self.sent = []
        for addr in (A, B):
            m = bf.Match()
            m.map_up = 1.0
            self._matches[addr] = m

    def _send_bundle(self, addr, data, seq, bf_key):
        self.sent.append((addr, data))


@pytest.fixture
def room(bf, monkeypatch):
    import match_room
    monkeypatch.setattr(match_room, "RELAY_HZ", 1e9)
    monkeypatch.setattr(match_room, "_log", quiet)
    return match_room


def _pos_msg(x, y, z):
    return (2, struct.pack("<3f3f", x, y, z, 0.0, 0.0, 0.0))


def test_room_join_shares_one_room_and_public_ids(bf, room):
    gate = FakeGate(bf)
    ra = room.join(gate, A, "Ann", 1, 1, None)
    rb = room.join(gate, B, "Bob", 2, 1, None)
    assert ra is rb and room.BY_ADDR[A] is ra
    assert [(m.slot, m.public_id) for m in ra.members] == [(0, room.PUBLIC_BASE), (1, room.PUBLIC_BASE + 1)]
    assert ra.views(ra.member(A)) == [(B, room.PUBLIC_BASE)]


def test_room_solo_mode_gives_each_client_its_own_room(bf, room, monkeypatch):
    monkeypatch.setenv("ROOM_MODE", "solo")
    gate = FakeGate(bf)
    assert room.join(gate, A, "Ann", 1, 1, None) is not room.join(gate, B, "Bob", 2, 1, None)


def test_room_spawn_then_relay_then_leave(bf, room):
    gate = FakeGate(bf)
    r = room.join(gate, A, "Ann", 1, 1, None)
    room.join(gate, B, "Bob", 2, 1, None)
    room.on_client_msgs(gate, B, [_pos_msg(500.0, 10.0, 500.0)])     # B settled on the map
    gate.sent.clear()
    room.on_client_msgs(gate, A, [_pos_msg(100.0, 20.0, 100.0)])
    ann = r.member(A)
    assert ann.pos == (100.0, 20.0, 100.0)
    created = [d for addr, d in gate.sent if addr == B]
    assert created == [room.avatar_create(room.PUBLIC_BASE, r, ann, ann.pos, ann.dir)]
    assert created[0].startswith(bf.enter_aoi(room.PUBLIC_BASE))
    assert room.PUBLIC_BASE in r.seen[B]

    gate.sent.clear()
    room.on_client_msgs(gate, A, [(3, u32(0) + u32(0) + struct.pack("<3f3f", 110.0, 20.0, 100.0, 0, 0, 0.5))])
    assert ann.pos == (110.0, 20.0, 100.0)                          # msg 3: spaceID, vehicleID first
    assert (B, bf.detailed_position(room.PUBLIC_BASE, ann.pos, ann.dir)) in gate.sent

    gate.sent.clear()
    room.leave(gate, A)
    assert gate.sent == [(B, bf.leave_aoi(room.PUBLIC_BASE))]
    room.leave(gate, B)
    assert room.ROOMS == [] and room.BY_ADDR == {}


def test_room_waits_for_the_viewer_to_stand_on_the_map(bf, room):
    gate = FakeGate(bf)
    room.join(gate, A, "Ann", 1, 1, None)
    room.join(gate, B, "Bob", 2, 1, None)
    room.on_client_msgs(gate, A, [_pos_msg(100.0, 20.0, 100.0)])     # B has not reported a position yet
    assert gate.sent == []


def test_room_relays_all_clients_props_with_the_public_id(bf, room):
    gate = FakeGate(bf)
    r = room.join(gate, A, "Ann", 1, 1, None)
    room.join(gate, B, "Bob", 2, 1, None)
    r.seen.setdefault(B, set()).add(room.PUBLIC_BASE)
    gate.sent.clear()
    room.on_reply(gate, A, bf.prop_update("BattleGroundAvatar", bf.AVATAR_ID, "pose", bf.i8(2)))   # ALL_CLIENTS
    assert gate.sent == [(B, bf.prop_update("BattleGroundAvatar", room.PUBLIC_BASE, "pose", bf.i8(2)))]
    gate.sent.clear()
    room.on_reply(gate, A, bf.prop_update("BattleGroundAvatar", bf.AVATAR_ID, "fallPhase", bf.i8(3)))  # own only
    assert gate.sent == []

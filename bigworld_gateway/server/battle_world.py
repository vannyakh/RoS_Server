"""World entities in a match (lane 5): land vehicles (checklist 15.x) and the supply drop (16.x).

Protocol (docs/LOBBY_FINDINGS.md, "World entities"):

Vehicles. A car is a `LandCar` entity (client type from client_entity_types.json). The client picks the
model from `tpsVehicleID` (legacyProperties.getVehicleData) and the vehicle data from `characterType`
(getLandVehicleData). The player asks to get in with its own cell methods
BattleGroundAvatar.reqGetOnLandVehicleAsDriver(ENTITY_ID) / ...AsPassenger / reqGetOffLandVehicle /
reqSwitchToSeat(INT32); the vehicle's own cell methods reqDriver / reqGetOff are server-internal.
The server answers with
  vehicle props   driverID, hasDriver, usedHangSockets [{sockname, id}]
  vehicle calls   onAddAvatarSocket(STRING sockname, ENTITY_ID) -> iVehicleEntity binds the avatar to the seat,
                  onControlledBy(ENTITY_ID, BOOL) -> the driver's client loads the first-person (physics) parts
  ClientInterface controlEntity (0x5A, fixed 5: id u32 + bool) -> BigWorld lets the client move the vehicle
  avatar props    vehicleEntID, inLandVehicle, isLandDriver, inVehicle, isDriver -> iLandDrive.refreshDriveState
                  -> onSwitchToDriver (driving HUD)
Driving is client physics: the driver's client reports the controlled vehicle with avatarUpdateExplicit
(msg 3, entity id first), which the server tracks (15.12) and relays (lane 6).

Supply drop. The aircraft is a `Plane` with `mode` other than PlaneWorkMode PEOPLE / REBORN (the client then
loads AIRDROP_PLANE_MODEL, tps/car/airplane_airdrop), flown like the transport plane (detailedPosition).
The crate is a `DtsPlayerHeritage` with `drop` = 1 (supply-box model AIR_DROP_MODEL) and `dropping` = 1
(parachute + AvatarDropFilter, descends with detailedPosition); `dropping` 0 removes the parachute on landing.
Its loot is the `items` PY_DICT; the client picks up with DtsPlayerHeritage.tryPickUp(UUID, INT32, BOOL).

Entity ids 26000-26999 (lane 6 uses 11000-11199 and 12000+ for bots, props are 30000+).
Hooks in battle_flow.py: entity_type_of, Match.on_message, Match.handle (one line each).
"""
import math
import os
import pickle
import struct
import time

import bwdefs
import battle_flow as bf

VEHICLE_BASE = 26000          # 26000-26099 vehicles
CRATE_BASE = 26100            # 26100-26199 supply crates
AIRDROP_PLANE_ID = 26500

MSG_CONTROL_ENTITY = 0x5A     # message_map seq 111 - 21, fixed 5
MSG_AVATAR_UPDATE_EXPLICIT = 3

# ---- tunables (env); values marked (probe) wait for client/frida/payloads/world_entities_probe.py ------
VEHICLES = os.environ.get("WORLD_VEHICLES", "off") == "on"      # opt-in until verified on device
VEHICLE_ENTITY = os.environ.get("VEHICLE_ENTITY", "LandCar")
VEHICLE_CHAR = int(os.environ.get("VEHICLE_CHAR", "1"))               # characterType (probe)
VEHICLE_TPS = int(os.environ.get("VEHICLE_TPS", "1"))                 # tpsVehicleID (probe)
VEHICLE_HP = int(os.environ.get("VEHICLE_HP", "1000"))
VEHICLE_FUEL = float(os.environ.get("VEHICLE_FUEL", "100"))
VEHICLE_SPEED = float(os.environ.get("VEHICLE_SPEED", "30"))
VEHICLE_OFFSET = tuple(float(v) for v in os.environ.get("VEHICLE_OFFSET", "60,0,60").split(","))
VEHICLE_SPAWN_DELAY = float(os.environ.get("VEHICLE_SPAWN_DELAY", "3"))   # s after landing
DRIVER_SOCKET = os.environ.get("VEHICLE_DRIVER_SOCKET", "driver")      # const.VEHICLE_DRIVER_SOCKET (probe)
PASSENGER_SOCKETS = os.environ.get("VEHICLE_PASSENGER_SOCKETS", "hang_0,hang_1,hang_2").split(",")
CONTROL_ENTITY = os.environ.get("VEHICLE_CONTROL", "on") != "off"

AIRDROP = os.environ.get("WORLD_AIRDROP", "off") == "on"        # opt-in until verified on device
AIRDROP_DELAY = float(os.environ.get("AIRDROP_DELAY", "60"))           # s after the zone starts
AIRDROP_MODE = int(os.environ.get("AIRDROP_PLANE_MODE", "2"))          # PlaneWorkMode, not PEOPLE (1) (probe)
AIRDROP_SPEED = float(os.environ.get("AIRDROP_SPEED", "500"))
AIRDROP_HALF = float(os.environ.get("AIRDROP_HALF", "6000"))           # route half length through the drop point
AIRDROP_PLANE_HEIGHT = float(os.environ.get("AIRDROP_PLANE_HEIGHT", "3000"))   # above the drop point's ground
AIRDROP_FALL_SPEED = float(os.environ.get("AIRDROP_FALL_SPEED", "80"))  # units/s while the crate descends
AIRDROP_OFFSET = tuple(float(v) for v in os.environ.get("AIRDROP_OFFSET", "150,150").split(","))  # from the player
AIRDROP_HERITAGE_MODE = int(os.environ.get("AIRDROP_HERITAGE_MODE", "0"))      # const.HeritageMode (probe)
AIRDROP_ITEMS = os.environ.get("AIRDROP_ITEMS", "1003:1,7:1,10:1,103:2,1103:60")   # propID:amount (lane 4 ids)
AIRDROP_ITEM_FORMAT = os.environ.get("AIRDROP_ITEM_FORMAT", "dict")    # dict | tuple (probe: dis of the UI)
POS_EVERY = 0.2


def entity_type(eid):
    """Client entity type of a lane 5 id, or None (battle_flow.entity_type_of hook)."""
    if VEHICLE_BASE <= eid < CRATE_BASE:
        return VEHICLE_ENTITY
    if CRATE_BASE <= eid < CRATE_BASE + 100:
        return "DtsPlayerHeritage"
    if eid == AIRDROP_PLANE_ID:
        return "Plane"
    return None


# ---- encoders ---------------------------------------------------------------------------------
def b8(v): return struct.pack("<B", 1 if v else 0)
def u32(v): return struct.pack("<I", v)
def string(s): return bwdefs.blob(s.encode("utf-8") if isinstance(s, str) else s)


def socket_list(seats):
    """ARRAY <of> VEHICLE_SOCKET_INFO {sockname STRING, id UINT32} (array count as battle_flow.arr_*)."""
    return struct.pack("<I", len(seats)) + b"".join(string(s) + u32(i) for s, i in seats)


def control_entity(eid, on):
    return bytes([MSG_CONTROL_ENTITY]) + struct.pack("<IB", eid, 1 if on else 0)


def prop_update_long(entity, eid, name, value):
    """Property update for values over 255 bytes: battle_flow.prop_update's var8 form (0xC0 | idx) cannot
    carry them, so always use its var16 0xFD + bit-path form (same index list)."""
    lst = bf.update_prop_list(entity)
    idx = [p[0] for p in lst].index(name)
    total = (len(lst) - 1).bit_length() + 1
    nbytes = (total + 7) // 8
    path = ((idx << 1) << (8 * nbytes - total)).to_bytes(nbytes, "big")
    return bf._var16(0xFD, struct.pack("<I", eid) + path + value)


def avatar(name, value):
    return bf.prop_update("BattleGroundAvatar", bf.AVATAR_ID, name, value)


def vprop(vid, name, value):
    return bf.prop_update(VEHICLE_ENTITY, vid, name, value)


# ---- per-match state ------------------------------------------------------------------------------
def state(match):
    w = match.__dict__.get("world")
    if w is None:
        w = match.world = {"vehicles": {}, "next_vehicle": VEHICLE_BASE, "crates": {}, "next_crate": CRATE_BASE,
                           "vehicle_spawned": False, "airdrop": None, "airdrops": 0, "seat": None,
                           "last_vpos_log": 0.0}
    return w


def _log_pos(p):
    return "(%.0f, %.0f, %.0f)" % tuple(p)


# ---- vehicles -------------------------------------------------------------------------------------
def spawn_vehicle(match, pos, yaw=0.0, log=print):
    """createEntity of one LandCar at `pos` (15.01, 15.02)."""
    w = state(match)
    vid = w["next_vehicle"]
    w["next_vehicle"] += 1
    w["vehicles"][vid] = {"pos": tuple(pos), "yaw": yaw, "driver": 0, "seats": [], "hp": VEHICLE_HP,
                          "fuel": VEHICLE_FUEL, "moves": 0}
    log("      [WORLD] vehicle %d (%s char %d tps %d) at %s" % (vid, VEHICLE_ENTITY, VEHICLE_CHAR, VEHICLE_TPS, _log_pos(pos)))
    return bf.create_entity(vid, VEHICLE_ENTITY, pos=pos, direction=(yaw, 0.0, 0.0), values={
        "mapID": bf.i32(match.map_id), "characterType": u32(VEHICLE_CHAR), "tpsVehicleID": bf.i32(VEHICLE_TPS),
        "hp": bf.i32(VEHICLE_HP), "actualHP": bf.i32(VEHICLE_HP), "maxHp": bf.i32(VEHICLE_HP), "vHasHp": b8(1),
        "bActive": b8(1), "enabled": b8(1), "fuelAmount": bf.f32(VEHICLE_FUEL), "capacity": bf.f32(VEHICLE_FUEL),
        "fuelFull": b8(1), "maxSpeed": bf.f32(VEHICLE_SPEED), "basicMaxSpeed": bf.f32(VEHICLE_SPEED),
        "topSpeedClient": bf.f32(VEHICLE_SPEED), "canDriveOutWater": b8(1)})


def _seat_messages(vid, v):
    """Vehicle state after a seat change: driverID, hasDriver, usedHangSockets."""
    return (vprop(vid, "driverID", u32(v["driver"])) + vprop(vid, "hasDriver", b8(v["driver"]))
            + vprop(vid, "usedHangSockets", socket_list(v["seats"])))


def get_on(match, vid, driver, log=print):
    """reqGetOnLandVehicleAsDriver / AsPassenger (15.04, 15.05)."""
    w = state(match)
    v = w["vehicles"].get(vid)
    if v is None:
        log("      [WORLD] get on: unknown vehicle %d" % vid)
        return b""
    me = bf.AVATAR_ID
    if any(i == me for _, i in v["seats"]):
        return b""
    if driver and not v["driver"]:
        sock = DRIVER_SOCKET
        v["driver"] = me
    else:
        used = {s for s, _ in v["seats"]}
        sock = next((s for s in PASSENGER_SOCKETS if s not in used), None)
        driver = False
        if sock is None:
            log("      [WORLD] vehicle %d is full" % vid)
            return b""
    v["seats"].append((sock, me))
    w["seat"] = (vid, sock)
    log("      [WORLD] get on vehicle %d as %s (socket %s)" % (vid, "driver" if driver else "passenger", sock))
    out = _seat_messages(vid, v)
    out += bf.client_call(VEHICLE_ENTITY, "onPlayerEnter", vid, u32(me))
    out += bf.client_call(VEHICLE_ENTITY, "onAddAvatarSocket", vid, string(sock) + u32(me))
    out += (avatar("vehicleEntID", u32(vid)) + avatar("inLandVehicle", b8(1)) + avatar("inVehicle", b8(1))
            + avatar("isLandDriver", b8(driver)) + avatar("isDriver", b8(driver)))
    if driver:
        if CONTROL_ENTITY:
            out += control_entity(vid, True)
        out += bf.client_call(VEHICLE_ENTITY, "onControlledBy", vid, u32(me) + b8(1))
    return out


def get_off(match, vid, log=print, teleport=True):
    """reqGetOffLandVehicle (15.07): free the seat, stop client control, stand beside the car."""
    w = state(match)
    v = w["vehicles"].get(vid)
    me = bf.AVATAR_ID
    if v is None or not any(i == me for _, i in v["seats"]):
        return b""
    was_driver = v["driver"] == me
    sock = next(s for s, i in v["seats"] if i == me)
    v["seats"] = [(s, i) for s, i in v["seats"] if i != me]
    if was_driver:
        v["driver"] = 0
    w["seat"] = None
    x, y, z = v["pos"]
    side = (x + 25.0 * math.cos(v["yaw"]), y + 5.0, z - 25.0 * math.sin(v["yaw"]))
    log("      [WORLD] get off vehicle %d (socket %s) at %s" % (vid, sock, _log_pos(side)))
    out = b""
    if was_driver:
        out += bf.client_call(VEHICLE_ENTITY, "onUncontrolledBy", vid, u32(me))
        if CONTROL_ENTITY:
            out += control_entity(vid, False)
    out += bf.client_call(VEHICLE_ENTITY, "onDelAvatarSocket", vid, string(sock) + u32(me))
    out += bf.client_call(VEHICLE_ENTITY, "onPlayerLeave", vid, u32(me))
    out += _seat_messages(vid, v)
    out += (avatar("isDriver", b8(0)) + avatar("isLandDriver", b8(0)) + avatar("inVehicle", b8(0))
            + avatar("inLandVehicle", b8(0)) + avatar("vehicleEntID", u32(0)))
    return out + (bf.forced_position(bf.AVATAR_ID, side) if teleport else b"")


def switch_seat(match, seat_index, log=print):
    """reqSwitchToSeat(INT32) (15.06): 0 = driver, n = n-th passenger socket."""
    w = state(match)
    if not w["seat"]:
        return b""
    vid, _ = w["seat"]
    return get_off(match, vid, log, teleport=False) + get_on(match, vid, seat_index == 0, log)


def on_vehicle_update(match, payload, log=print):
    """avatarUpdateExplicit (msg 3) with a vehicle's id: the driver's client moves the car (15.08-15.12)."""
    if len(payload) < 20:
        return
    eid = struct.unpack_from("<I", payload)[0]
    v = state(match)["vehicles"].get(eid)
    if v is None:
        return
    x, y, z = struct.unpack_from("<3f", payload, 8)
    old = v["pos"]
    v["pos"] = (x, y, z)
    v["moves"] += 1
    if len(payload) >= 24:
        v["yaw"] = struct.unpack_from("<f", payload, 20)[0]
    now = time.time()
    w = state(match)
    if now - w["last_vpos_log"] >= 2.0:
        w["last_vpos_log"] = now
        d = math.dist(old, v["pos"]) if hasattr(math, "dist") else 0.0
        log("      [WORLD] vehicle %d moved to %s (report %d, step %.1f, raw %s)"
            % (eid, _log_pos(v["pos"]), v["moves"], d, payload[:8].hex()))


# ---- supply drop ----------------------------------------------------------------------------------
def _items():
    out = []
    for part in AIRDROP_ITEMS.split(","):
        if ":" in part:
            pid, amount = part.split(":")
            out.append((int(pid), int(amount)))
    return out


def crate_items(items):
    """items PY_DICT for DtsPlayerHeritage: {uuid: item} (item layout from the client UI, see FINDINGS)."""
    d = {}
    for uuid, (pid, amount) in items.items():
        d[uuid] = {"itemID": pid, "id": pid, "propID": pid, "amount": amount} if AIRDROP_ITEM_FORMAT == "dict" \
            else (pid, amount)
    return bwdefs.blob(pickle.dumps(d, protocol=2))


def airdrop_start(match, now, log=print):
    """Spawn the supply plane on a straight route over the drop point (16.01-16.03)."""
    w = state(match)
    px, py, pz = match.pos if getattr(match, "pos", None) else bf.FLIGHT_START
    ground = py
    drop = (px + AIRDROP_OFFSET[0], ground, pz + AIRDROP_OFFSET[1])
    y = ground + AIRDROP_PLANE_HEIGHT
    a = math.radians(float(os.environ.get("AIRDROP_HEADING", "45")))
    start = (drop[0] - AIRDROP_HALF * math.sin(a), y, drop[2] - AIRDROP_HALF * math.cos(a))
    end = (drop[0] + AIRDROP_HALF * math.sin(a), y, drop[2] + AIRDROP_HALF * math.cos(a))
    w["airdrop"] = {"start": start, "end": end, "drop": drop, "t0": now, "last": 0.0, "released": None,
                    "done": False, "yaw": a}
    w["airdrops"] += 1
    log("      [WORLD] supply drop %d: plane %s -> %s, drop point %s (mode %d)"
        % (w["airdrops"], _log_pos(start), _log_pos(end), _log_pos(drop), AIRDROP_MODE))
    return bf.create_entity(AIRDROP_PLANE_ID, "Plane", pos=start, direction=(a, 0.0, 0.0), values={
        "mapID": bf.i32(match.map_id), "moveSpeed": bf.f32(AIRDROP_SPEED), "inJumpArea": bf.i8(0),
        "mode": bf.i32(AIRDROP_MODE), "movePath": bf.arr_vec3([start, end])})


def _release_crate(match, pos, log):
    """DtsPlayerHeritage with drop + dropping at the plane (16.04)."""
    w = state(match)
    cid = w["next_crate"]
    w["next_crate"] += 1
    items = {os.urandom(16): it for it in _items()}
    w["crates"][cid] = {"pos": tuple(pos), "items": items, "landed": False, "opened": False}
    log("      [WORLD] crate %d released at %s, %d items" % (cid, _log_pos(pos), len(items)))
    return bf.create_entity(cid, "DtsPlayerHeritage", pos=pos, values={
        "mapID": bf.i32(match.map_id), "items": crate_items(items), "name": string("Airdrop"),
        "drop": b8(1), "dropping": b8(1), "heritageMode": bf.i32(AIRDROP_HERITAGE_MODE),
        "moveSpeed": bf.f32(AIRDROP_FALL_SPEED)})


def airdrop_tick(match, now, log=print):
    """Fly the plane, release over the drop point, lower the crate, land it (16.03-16.06)."""
    w = state(match)
    ad = w["airdrop"]
    if not ad or ad["done"] or now - ad["last"] < POS_EVERY:
        return b""
    ad["last"] = now
    out = b""
    (x1, y, z1), (x2, _, z2) = ad["start"], ad["end"]
    length = math.hypot(x2 - x1, z2 - z1)
    k = min((now - ad["t0"]) * AIRDROP_SPEED / max(length, 1.0), 1.0)
    if not ad.get("plane_gone"):
        ppos = (x1 + (x2 - x1) * k, y, z1 + (z2 - z1) * k)
        out += bf.detailed_position(AIRDROP_PLANE_ID, ppos, (0.0, 0.0, ad["yaw"]))
        if ad["released"] is None and k >= 0.5:
            ad["released"] = {"id": w["next_crate"], "y": y, "t": now}
            out += _release_crate(match, ppos, log)
        if k >= 1.0:
            ad["plane_gone"] = True
            log("      [WORLD] supply plane left the map")
            out += bf.leave_aoi(AIRDROP_PLANE_ID)
    rel = ad["released"]
    if rel is not None:
        crate = w["crates"][rel["id"]]
        dx, ground, dz = ad["drop"]
        cy = max(rel["y"] - (now - rel["t"]) * AIRDROP_FALL_SPEED, ground)
        crate["pos"] = (dx, cy, dz)
        out += bf.detailed_position(rel["id"], crate["pos"], (0.0, 0.0, 0.0))
        if cy <= ground and not crate["landed"]:
            crate["landed"] = True
            log("      [WORLD] crate %d landed at %s" % (rel["id"], _log_pos(crate["pos"])))
            out += bf.prop_update("DtsPlayerHeritage", rel["id"], "dropping", b8(0))
    if ad.get("plane_gone") and (rel is None or w["crates"][rel["id"]]["landed"]):
        ad["done"] = True
    return out


def crate_pickup(match, cid, args, log=print):
    """DtsPlayerHeritage.tryPickUp(UUID, INT32 amount, BOOL) (16.08, 16.09)."""
    crate = state(match)["crates"].get(cid)
    if crate is None or len(args) < 1:
        return b""
    n = args[0]                                        # BLOB: packed length (< 255) + bytes
    uuid, rest = args[1:1 + n], args[1 + n:]
    want = struct.unpack_from("<i", rest)[0] if len(rest) >= 4 else 0
    if uuid not in crate["items"]:
        log("      [WORLD] crate %d: unknown item %s" % (cid, uuid.hex()))
        return b""
    pid, amount = crate["items"][uuid]
    take = amount if want <= 0 else min(want, amount)
    if take >= amount:
        del crate["items"][uuid]
    else:
        crate["items"][uuid] = (pid, amount - take)
    crate["opened"] = True
    match.collected = getattr(match, "collected", 0) + 1
    log("      [WORLD] crate %d: picked prop %d x%d (%d items left)" % (cid, pid, take, len(crate["items"])))
    info = bwdefs.blob(pickle.dumps({"ex_tm": 0}, protocol=2))
    item = bwdefs.blob(uuid) + bf.i32(take) + info + bf.i32(0)
    add = bf.i32(pid) + struct.pack("<I", 1) + item + bf.i8(0) + bf.i32(0)
    items = crate_items(crate["items"])
    upd = (bf.prop_update if len(items) + 4 <= 255 else prop_update_long)("DtsPlayerHeritage", cid, "items", items)
    return (upd + bf.client_call("DtsPlayerHeritage", "resetItems", cid)
            + bf.client_call("BattleGroundAvatar", "onAddDtsItem", bf.AVATAR_ID, add)
            + bf.client_call("BattleGroundAvatar", "onPickUpPropEntity", bf.AVATAR_ID))


# ---- hooks (called from battle_flow.Match) ---------------------------------------------------------
def on_message(match, msgid, payload, log=print):
    """Every client message: vehicle position reports, vehicle spawn after landing, airdrop timeline."""
    w = state(match)
    now = time.time()
    if msgid == MSG_AVATAR_UPDATE_EXPLICIT and w["vehicles"]:
        on_vehicle_update(match, payload, log)
    if VEHICLES and not w["vehicle_spawned"] and getattr(match, "stage", None) == "landed" \
            and getattr(match, "pos", None) and now - getattr(match, "stage_time", now) >= VEHICLE_SPAWN_DELAY:
        w["vehicle_spawned"] = True
        x, y, z = match.pos
        return spawn_vehicle(match, (x + VEHICLE_OFFSET[0], y + VEHICLE_OFFSET[1] + 2.0, z + VEHICLE_OFFSET[2]), log=log)
    zone = getattr(match, "zone", None)
    if zone and not w.get("zone_seen"):
        w["zone_seen"] = now
    if AIRDROP and zone and w["airdrop"] is None and now - w["zone_seen"] >= AIRDROP_DELAY * zone["scale"]:
        return airdrop_start(match, now, log)
    if w["airdrop"]:
        return airdrop_tick(match, now, log)
    return b""


def handle(match, eid, entity, name, args, log=print):
    """Cell requests for lane 5; None = not ours."""
    if entity == "BattleGroundAvatar" and name in ("reqGetOnLandVehicleAsDriver", "reqGetOnLandVehicleAsPassenger"):
        vid = struct.unpack_from("<I", args)[0] if len(args) >= 4 else 0
        return get_on(match, vid, name.endswith("Driver"), log)
    if entity == "BattleGroundAvatar" and name == "reqGetOffLandVehicle":
        vid = struct.unpack_from("<I", args)[0] if len(args) >= 4 else 0
        return get_off(match, vid, log)
    if entity == "BattleGroundAvatar" and name == "reqSwitchToSeat" and len(args) >= 4:
        return switch_seat(match, struct.unpack_from("<i", args)[0], log)
    if entity == "BattleGroundAvatar" and name == "reqSwitchToDriveLandVehicle":
        w = state(match)
        return switch_seat(match, 0, log) if w["seat"] else b""
    if entity == "DtsPlayerHeritage" and name == "tryPickUp":
        return crate_pickup(match, eid, args, log)
    if entity == VEHICLE_ENTITY and eid in state(match)["vehicles"]:
        log("      [WORLD] <- vehicle %d.%s args=%s" % (eid, name, args.hex()))
        return b""
    return None


def debug(match, parts, log=print):
    """battle trigger lines (server/trigger_battle.txt) for lane 5:
      car [dx dz]      spawn a vehicle next to the player
      airdrop          start a supply drop now
      geton <vid> [p]  as if the client sent reqGetOnLandVehicleAsDriver (p = passenger)
      getoff <vid>     as if reqGetOffLandVehicle"""
    cmd = parts[0]
    if cmd == "car":
        x, y, z = match.pos or bf.FLIGHT_START
        dx, dz = (float(v) for v in parts[1:3]) if len(parts) >= 3 else (VEHICLE_OFFSET[0], VEHICLE_OFFSET[2])
        state(match)["vehicle_spawned"] = True
        return spawn_vehicle(match, (x + dx, y + 2.0, z + dz), log=log)
    if cmd == "airdrop":
        return airdrop_start(match, time.time(), log)
    if cmd == "geton":
        return get_on(match, int(parts[1]), not (len(parts) > 2 and parts[2] == "p"), log)
    if cmd == "getoff":
        return get_off(match, int(parts[1]), log)
    return None


# ---- hot reload (battle_flow is reloaded by ros_server; this module reloads itself the same way) -------
_MTIME = os.path.getmtime(__file__)


def _fresh():
    import importlib, sys
    mod = sys.modules[__name__]
    try:
        mt = os.path.getmtime(__file__)
    except OSError:
        return mod
    if mt != mod._MTIME:
        mod = importlib.reload(mod)
    return mod


def hook_message(match, msgid, payload, log=print):
    try:
        return _fresh().on_message(match, msgid, payload, log)
    except Exception as e:
        log("      [WORLD] on_message failed: %r" % (e,))
        return b""


def hook_handle(match, eid, entity, name, args, log=print):
    try:
        return _fresh().handle(match, eid, entity, name, args, log)
    except Exception as e:
        log("      [WORLD] %s failed: %r" % (name, e))
        return b""


def hook_entity_type(eid):
    return entity_type(eid)


def hook_debug(match, parts, log=print):
    try:
        return _fresh().debug(match, parts, log)
    except Exception as e:
        log("      [WORLD] debug %r failed: %r" % (parts, e))
        return b""

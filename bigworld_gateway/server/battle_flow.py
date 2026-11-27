"""Battle flow for the original client: the space entity (safe zone), the plane, and the
countdown -> plane -> jump -> zone timeline.

ClientInterface wire ids are extract/message_map.txt seq - 21 (id 0 = authenticate):
  7 spaceData (var16), 9 createEntity (var16), 10 updateEntity (var16), 11 enterAoI (fixed 5),
  15 leaveAoI (var16), 0x58 detailedPosition (fixed 30), 0x59 forcedPosition (fixed 36).
Entity messages: 0x80 | index = client method (ros_server.client_method_ex),
0xC0 | index = property update (docs/ENTITY_PROPERTY_UPDATE_FORMAT.md; avatar verified live).

Verified createEntity layout (RO-056 / docs/CREATE_ENTITY_FRAMING.md): u32 id, u16 type,
3xf32 pos, 3xint8 packed yaw/pitch/roll, u8 flag=0, u8 compression=0, u8 mask_flag=1,
ceil(N/8) mask bytes, then OTHER/ALL_CLIENTS property values in list order.

Legacy experiment env switches (removed; do not reintroduce):
  CE_PROPS, CE_PREFIX — early property-stream experiments before the mask layout.
  CE_INDEX — toggled createEntity vs update property index lists.
  CE_DIR — alternate float32 direction packing (verified path is packed int8).
  CE_MASK / CE_ENTER_AOI — always-on verified defaults (mask + enterAoI).

The client reads the zone from Globals.spaceEntity, a BattleGroundSpace entity
(circleStage, whiteCircleCenter/Radius, blueCircle*), and the plane from the entity whose id is
the player's planeID (Plane: movePath, moveSpeed, inJumpArea).
"""
import json
import math
import os
import struct

import bwdefs

HERE = os.path.dirname(os.path.abspath(__file__))

MSG_CREATE_ENTITY = 9
MSG_ENTER_AOI = 11
MSG_LEAVE_AOI = 15
MSG_FORCED_POSITION = 0x59
NO_ID_ALIAS = 0xFF

# DataDescription flags that are sent to a client (own or other), i.e. clientServer properties.
CLIENT_FLAGS = ("ALL_CLIENTS", "OTHER_CLIENTS", "OWN_CLIENT", "BASE_AND_CLIENT", "CELL_PUBLIC_AND_OWN")
OTHER_CLIENT_FLAGS = ("ALL_CLIENTS", "OTHER_CLIENTS")

_DEFS = None
_TYPES = None


def defs():
    global _DEFS
    if _DEFS is None:
        _DEFS = bwdefs.Defs()
    return _DEFS


def client_type(name):
    global _TYPES
    if _TYPES is None:
        _TYPES = json.load(open(os.path.join(HERE, "extract", "client_entity_types.json")))
    return _TYPES.index(name)


def client_props(entity):
    """[(name, type, flags)] of the properties a client knows, in .def order (the index space
    of tagged property data and 0xC0 property updates)."""
    return [p[:3] for p in defs().properties(entity) if p[2] in CLIENT_FLAGS]


def other_client_props(entity):
    """The client's createEntity property list (docs/CREATE_ENTITY_FORMAT.md): .def parse order, a
    re-defined name keeps its FIRST position and takes its LAST definition (type and flags), then only
    ALL_CLIENTS / OTHER_CLIENTS. BattleGroundSpace = 92 entries, Plane = 8."""
    order, last = [], {}
    for p in defs().properties(entity):
        if p[0] not in last:
            order.append(p[0])
        last[p[0]] = p
    return [last[n][:3] for n in order if last[n][2] in OTHER_CLIENT_FLAGS]


def prop_index(entity, name):
    """Index in the createEntity OTHER/ALL_CLIENTS list (desc+0x88). For 0xC0 updates use
    update_prop_list instead (desc+0x70)."""
    for i, p in enumerate(other_client_props(entity)):
        if p[0] == name:
            return i
    raise KeyError(f"{entity}.{name} is not an ALL_CLIENTS/OTHER_CLIENTS property")


def _var16(msgid, payload):
    return bytes([msgid]) + struct.pack("<H", len(payload)) + payload


def enter_aoi(eid, alias=NO_ID_ALIAS):
    return bytes([MSG_ENTER_AOI]) + struct.pack("<IB", eid, alias)


def leave_aoi(eid):
    return _var16(MSG_LEAVE_AOI, struct.pack("<I", eid))


def _direction(yaw, pitch, roll):
    # PackedYawPitchRoll<false>: angle / pi * 128 as int8 (RO-056 verified).
    q = lambda a: max(-128, min(127, int(round(a / math.pi * 128))))
    return struct.pack("<3b", q(yaw), q(pitch), q(roll))


def prop_data(entity, values):
    """Bytes after the 3 direction bytes of createEntity (verified RO-056 layout):
    [flag u8 = 0][compression u8 = 0][mask flag u8 = 1][ceil(N/8) mask][selected values].
    Mask bit i set = property i uses the .def default (not on the stream)."""
    props = other_client_props(entity)
    names = [p[0] for p in props]
    for n in values:
        if n not in names:
            raise KeyError(f"{entity}.{n} is not an ALL_CLIENTS/OTHER_CLIENTS property")
    mask, body = bytearray((len(props) + 7) // 8), b""
    for i, (name, typ, flags) in enumerate(props):
        if name in values:
            body += values[name]
        else:
            mask[i >> 3] |= 1 << (i & 7)
    return bytes([0, 0, 1]) + bytes(mask) + body


def create_entity(eid, entity, pos=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 0.0), values=None):
    """enterAoI + createEntity for a non-player entity (verified RO-056 framing)."""
    payload = (struct.pack("<IH", eid, client_type(entity)) + struct.pack("<3f", *pos)
               + _direction(*direction) + prop_data(entity, values or {}))
    return enter_aoi(eid) + _var16(MSG_CREATE_ENTITY, payload)


# ---- value encoders -------------------------------------------------------------------------
def i8(v): return struct.pack("<b", v)
def i32(v): return struct.pack("<i", v)
def f32(v): return struct.pack("<f", v)
def vec2(x, y): return struct.pack("<2f", x, y)
def vec3(x, y, z): return struct.pack("<3f", x, y, z)
def arr_i32(vals): return struct.pack("<I", len(vals)) + b"".join(i32(v) for v in vals)
def arr_vec3(vals): return struct.pack("<I", len(vals)) + b"".join(vec3(*v) for v in vals)


# ---- flight sequence --------------------------------------------------------------------------
# After the PREPARE countdown: (delay in seconds after it ends, debug_command lines). {stage} is the game
# clock (BigWorld.serverTime) at send time. Observed on the client: planeID puts the player in the
# plane UI ("N Onboard", jump button, PARAGLIDER / PARACHUTE), gameStatus 2 (BEFORE_FIGHT) removes the
# countdown banner, and with planeID back to 0, fallPhase 2 (CAN_FALL) and the player lifted in the air the
# client falls on its own physics. The plane does not carry the player yet: the position is a fixed point.
FLIGHT_START = (698.0, 19300.0, -373.0)
FLIGHT_STEPS = (
    (0.0, ("plane", "setp planeID %d" % int(os.environ.get("PLANE_ENTITY_ID", "20002")))),
    (1.0, ("leave %d" % int(os.environ.get("SPACE_ENTITY_ID", "20001")), "spaces 2 {stage}")),
    (2.5, ("setp planeID 0", "tp %s %s %s" % FLIGHT_START, "setp fallPhase 2")),
)


# ---- test trigger ---------------------------------------------------------------------------
SPACE_ID = int(os.environ.get("SPACE_ENTITY_ID", "20001"))
PLANE_ID = int(os.environ.get("PLANE_ENTITY_ID", "20002"))


def debug_command(line, map_id=700, match=None):
    """One line of server/trigger_battle.txt -> bytes to send (experiments on a live match).
      space0          BattleGroundSpace with no properties
      space           BattleGroundSpace with mapID and a circle at the player's area
      leave <eid>     leaveAoI
      raw <hex>       raw ClientInterface bytes"""
    parts = line.split()
    if not parts:
        return b""
    cmd = parts[0]
    if cmd == "space0":                 # default dictionary only (framing check)
        return create_entity(SPACE_ID, "BattleGroundSpace")
    if cmd == "spacemap":               # mapID only: should get enterWorld past the maps_utils failure
        return create_entity(SPACE_ID, "BattleGroundSpace", values={"mapID": i32(map_id)})
    if cmd == "tp":                     # tp <x> <y> <z> [spaceID]: forcedPosition (0x59, fixed 36) of the own player
        x, y, z = (float(v) for v in parts[1:4])
        space_id = int(parts[4]) if len(parts) > 4 else 1
        # entity id, spaceID, vehicleID, position (3 x float32), direction (3 x float32)  [layout: unverified]
        return bytes([MSG_FORCED_POSITION]) + struct.pack("<III3f3f", AVATAR_ID, space_id, 0, x, y, z, 0.0, 0.0, 0.0)
    if cmd == "spaces":                 # spaces <gameStatus 0-4> <stage start> [x z]: space in a given game status
        x, z = (float(v) for v in (parts[3:5] if len(parts) >= 5 else (845.0, -2467.0)))
        return create_entity(SPACE_ID, "BattleGroundSpace", values={
            "mapID": i32(map_id), "gameStatus": i32(int(parts[1])), "aliveNum": i32(100), "circleStage": i32(1),
            "gameStageStartTime": f32(float(parts[2])),
            "whiteCircleCenter": vec2(x, z), "whiteCircleRadius": i32(300),
            "blueCircleCenter": vec2(x, z), "blueCircleRadius": i32(1200),
            "blueCircleStartCenter": vec2(x, z), "blueCircleStartRadius": i32(1200),
            "planeEntityIDs": arr_i32([PLANE_ID])})
    if cmd == "spacet":                 # spacet <now|real|seconds> [x z]: space with gameStageStartTime set
        x, z = (float(v) for v in (parts[2:4] if len(parts) >= 4 else (845.0, -2467.0)))
        when = parts[1] if len(parts) > 1 else "now"
        if when == "now":               # the game clock the client was given by syncServerTime
            import athlete_requests
            stamp = float(athlete_requests.game_now())
        elif when == "real":
            import time
            stamp = time.time()
        else:
            stamp = float(when)
        return create_entity(SPACE_ID, "BattleGroundSpace", values={
            "mapID": i32(map_id), "gameStatus": i32(1), "aliveNum": i32(100), "circleStage": i32(1),
            "gameStageStartTime": f32(stamp),
            "whiteCircleCenter": vec2(x, z), "whiteCircleRadius": i32(300),
            "blueCircleCenter": vec2(x, z), "blueCircleRadius": i32(1200),
            "blueCircleStartCenter": vec2(x, z), "blueCircleStartRadius": i32(1200),
            "planeEntityIDs": arr_i32([PLANE_ID])})
    if cmd == "space":
        x, z = (float(v) for v in (parts[1:3] if len(parts) >= 3 else (845.0, -2467.0)))
        return create_entity(SPACE_ID, "BattleGroundSpace", values={
            "mapID": i32(map_id), "gameStatus": i32(1), "aliveNum": i32(100), "circleStage": i32(1),
            "whiteCircleCenter": vec2(x, z), "whiteCircleRadius": i32(300),
            "blueCircleCenter": vec2(x, z), "blueCircleRadius": i32(1200),
            "blueCircleStartCenter": vec2(x, z), "blueCircleStartRadius": i32(1200),
            "planeEntityIDs": arr_i32([PLANE_ID])})
    if cmd == "plane0":                 # Plane with the default dictionary (framing check)
        return create_entity(PLANE_ID, "Plane")
    if cmd == "plane":                  # Plane flying a two-point path at height 300
        return create_entity(PLANE_ID, "Plane", values={
            "mapID": i32(map_id), "moveSpeed": f32(60.0), "inJumpArea": i8(0), "mode": i32(0),
            "movePath": arr_vec3([(0.0, 300.0, 0.0), (2000.0, 300.0, 2000.0)])})
    if cmd == "ce":                     # ce <eid> <Entity> <raw prop-data hex>
        payload = (struct.pack("<IH", int(parts[1]), client_type(parts[2])) + struct.pack("<3f", 0, 0, 0)
                   + _direction(0, 0, 0) + bytes.fromhex("".join(parts[3:])))
        return enter_aoi(int(parts[1])) + _var16(MSG_CREATE_ENTITY, payload)
    if cmd == "loot" and match is not None:     # loot <x> <y> <z> [count]: ring of test props around a point
        import math
        x, y, z = (float(v) for v in parts[1:4])
        ids = [1001, 1101, 2200, 2300, 1002, 1102, 1301, 1401]
        n = int(parts[4]) if len(parts) > 4 else len(ids)
        out = b""
        for k in range(n):
            a = 2 * math.pi * k / max(n, 1)
            out += match.spawn_prop(ids[k % len(ids)], 1, (x + 3.0 * math.cos(a), y, z + 3.0 * math.sin(a)), map_id)
        return out
    if cmd == "pidx":                   # pidx <global index> <hex args> [eid]: entity message by raw index
        return indexed_call(int(parts[1]), int(parts[3]) if len(parts) > 3 else AVATAR_ID, bytes.fromhex(parts[2]))
    if cmd == "setp":                   # setp <name> <number>: own player INT8 / INT32 / FLOAT property
        kind = dict((q[0], q[1]) for q in update_prop_list("BattleGroundAvatar")).get(parts[1])
        enc = {"INT8": lambda v: i8(int(v)), "INT32": lambda v: i32(int(v)), "FLOAT": lambda v: f32(float(v))}.get(kind)
        if enc is None:
            raise ValueError("setp: property %r has type %r (INT8, INT32 and FLOAT only)" % (parts[1], kind))
        return prop_update("BattleGroundAvatar", AVATAR_ID, parts[1], enc(parts[2]))
    if cmd == "wpn":                    # wpn <slot 1|2> <weaponID>: put a gun in a slot, make it current, wear it
        slot, wid = int(parts[1]), int(parts[2])
        return (prop_update("BattleGroundAvatar", AVATAR_ID, "dtsWeapon%d" % slot, weapon_item(wid))
                + prop_update("BattleGroundAvatar", AVATAR_ID, "dtsCurWeapon", i32(slot))
                + client_call("BattleGroundAvatar", "onWearDtsWeapon", AVATAR_ID, i32(slot)))
    if cmd == "leave":
        return leave_aoi(int(parts[1]))
    if cmd == "raw":
        return bytes.fromhex("".join(parts[1:]))
    raise ValueError(f"unknown battle trigger {cmd!r}")


# ---- in-battle client requests and replies --------------------------------------------------
# Client -> server cell-method call: msg id 0x80 | k (var16), payload = target entity id u32 + args.
# k is the position in the target type's exposed cell-method list (verified: openElement = 0x88,
# closeElement = 0x89 on BattleGroundSpace). Server -> client call: same framing, k from the
# type's client-method list (client_method_ex scheme for long lists).
AVATAR_ID = int(os.environ.get("AVATAR_ID", "10003"))
# client index - raw .def index, measured per method where it differs from the entity default
# (onAddItemToTemporary ran when sending raw 420 + 2... see docs/LOBBY_FINDINGS.md section 10)
CM_DELTAS = {"BattleGroundAvatar": {"onAddItem": 2}}
PROP_BASE = 30000
_CACHE = {}


def entity_type_of(eid):
    if eid == SPACE_ID:
        return "BattleGroundSpace"
    if eid == PLANE_ID:
        return "Plane"
    if eid >= PROP_BASE:
        return "DtsProp"
    return "BattleGroundAvatar"


def exposed_cell(entity):
    key = ("exp", entity)
    if key not in _CACHE:
        _CACHE[key] = [m for m in defs().methods(entity, "CellMethods") if m[2]]
    return _CACHE[key]


def client_methods(entity):
    key = ("cm", entity)
    if key not in _CACHE:
        # raw .def parse order. Measured on the client: for BattleGroundAvatar the client's index is the
        # raw index + 3 (sent raw 748 for onPickUpPropEntity, the client ran raw 745
        # onUpdateRos2WeaponReloadTimeScale). Space/Plane/DtsProp use offset 0 until measured otherwise.
        tab = defs().methods(entity, "ClientMethods")
        off = int(os.environ.get("CM_OFFSET_" + entity.upper(), 3 if entity == "BattleGroundAvatar" else 0))
        idx = {m[0]: i + off for i, m in reversed(list(enumerate(tab)))}
        for name, delta in CM_DELTAS.get(entity, {}).items():       # measured per method (offset is not constant)
            if name in idx:
                idx[name] = idx[name] - off + delta
        _CACHE[key] = (idx, len(tab) + off)
    return _CACHE[key]


def client_call(entity, name, eid, args=b""):
    """Server -> client method call on an entity (same message scheme as ros_server.client_method_ex)."""
    idx, n = client_methods(entity)
    i = idx[name]
    eff = 62 - (n + 192) // 255
    if i < eff:
        return _var16(0x80 | i, struct.pack("<I", eid) + args)
    k = i - eff
    return _var16(0x80 | (eff + (k >> 8)), struct.pack("<I", eid) + bytes([k & 0xFF]) + args)


def entity_method(eid, entity, name, args=b""):
    """RO-059 encoder: server -> client method on a non-player (or any) entity.
    Layout: 0x80|idx var16 + eid u32 + args (extended index when needed)."""
    return client_call(entity, name, eid, args)


def decode_request(msgid, payload):
    """(eid, entity, method name, arg bytes) for a client cell-method call, or None."""
    if not (0x80 <= msgid <= 0xBF) or len(payload) < 4:
        return None
    eid = struct.unpack_from("<I", payload)[0]
    entity = entity_type_of(eid)
    tab = exposed_cell(entity)
    j = msgid - 0x80
    eff = 62 - (len(tab) + 192) // 255          # same extended-index scheme as server->client calls
    args = payload[4:]
    if j < eff:
        k = j
    else:
        if not args:
            return eid, entity, "exposed#%d+?" % j, args
        k = eff + ((j - eff) << 8) + args[0]
        args = args[1:]
    # Measured: the client's BattleGroundAvatar exposed table is 2 entries ahead of the raw .def list at
    # least from index 205 up (onRecvClientFPS(30) arrived as 291 = raw 289, setPerspectPlayers([]) as
    # 207 = raw 205); `fire` (52) decoded right, so the shift starts between 53 and 205.
    if entity == "BattleGroundAvatar" and k >= int(os.environ.get("EXPOSED_SHIFT_FROM", "60")):
        k -= int(os.environ.get("EXPOSED_SHIFT", "2"))
    if k >= len(tab):
        return eid, entity, "exposed#%d" % k, args
    return eid, entity, tab[k][0], args


_PROP_TYPES = None


def prop_type(prop_id):
    """Client PROP_TYPE class name for a battle prop id ('Gun', 'Bullet', 'ColdWeapon', ...), or None."""
    global _PROP_TYPES
    if _PROP_TYPES is None:
        data = json.load(open(os.path.join(HERE, "extract", "battle_prop_types.json")))["types"]
        _PROP_TYPES = {i: t for t, ids in data.items() for i in ids}
    return _PROP_TYPES.get(prop_id)


NOISY = {"verifyClientValue", "onTryingToRun", "verifyClientWeaponValue", "checkAnticheatValue",
         "logAnticheatValue", "verifyClientConstantValue", "verifyClientCollisionValue", "verifyClientGameValue"}


class Match:
    """Server-side state of the current in-match world (doors, loot)."""

    def __init__(self):
        self.doors = {}          # elemID -> state
        self.props = {}          # eid -> (propID, amount)
        self.next_prop = PROP_BASE
        self.seen = set()
        self.gun_slots = {1: 0, 2: 0}    # weapon slot -> weaponID
        self.leave = False               # set by Quit Game; the gateway returns the client to the lobby
        self.pos = None                  # last (x, y, z) from the client's position message (msg 3)
        self.max_y = None                # highest y seen, to tell a fall from standing still
        self.still_since = None
        self.landed = False

    def spawn_prop(self, prop_id, amount, pos, map_id=700):
        eid = self.next_prop
        self.next_prop += 1
        self.props[eid] = (prop_id, amount)
        return create_entity(eid, "DtsProp", pos=pos, values={
            "mapID": i32(map_id), "propID": i32(prop_id), "amount": i32(amount)})

    def on_position(self, payload, now, log=print):
        """Client position message (msg 3: 8 header bytes, then x, y, z float32). Detects the end of the
        skydive (a long fall, then no vertical movement) and replies with fallPhase NORMAL / flightStage
        Ground so the client leaves the skydive pose. Measured: the client keeps its own physics, so it
        stops at the terrain by itself; the server only has to change state. Returns reply bytes."""
        if len(payload) < 20 or self.landed:
            return b""
        x, y, z = struct.unpack_from("<3f", payload, 8)
        last = self.pos
        self.pos = (x, y, z)
        self.max_y = y if self.max_y is None else max(self.max_y, y)
        if last is None or self.max_y - y < float(os.environ.get("LAND_MIN_FALL", "1000")):
            return b""
        if abs(y - last[1]) > 0.5:
            self.still_since = None
            return b""
        self.still_since = self.still_since or now
        if now - self.still_since < float(os.environ.get("LAND_STILL_SECS", "1.0")):
            return b""
        self.landed = True
        log("      [BATTLE] landed at (%.0f, %.0f, %.0f) -> fallPhase 0, flightStage 2" % (x, y, z))
        return (prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(0))
                + prop_update("BattleGroundAvatar", AVATAR_ID, "flightStage", i32(2)))

    def handle(self, msgid, payload, log=print):
        """Reply bytes (possibly empty) for one client message."""
        req = decode_request(msgid, payload)
        if req is None:
            return b""
        eid, entity, name, args = req
        self.seen.add((entity, name))
        if name not in NOISY:
            log("      [BATTLE] <- %s(%s).%s args=%s" % (entity, eid, name, args.hex()))
        if entity == "BattleGroundAvatar" and name == "changePose" and args:
            pose = struct.unpack("<b", args[:1])[0]
            if pose in (0, 1, 2):        # const.PlayerPose STAND, SQUAT, CRAWL
                return prop_update("BattleGroundAvatar", AVATAR_ID, "pose", i8(pose))
            return b""
        # Skydive / parachute. The client sends fall() once it is free-falling (after fallPhase 2 CAN_FALL)
        # and drives later phases itself with changeFallPhase / changeGlidePhase; the server applies them
        # to the own-client properties. const.FallPhase: NORMAL 0, BEFORE_FALL 1, CAN_FALL 2,
        # BEFORE_OPEN_PARACHUTE 3, CAN_OPEN_PARACHUTE 4, PARACHUTE_OPENED 5.
        if entity == "BattleGroundAvatar" and name == "fall":
            phase = int(os.environ.get("FALL_REPLY_PHASE", "3"))
            self.fall_phase = phase
            log("      [BATTLE] fall -> fallPhase %d" % phase)
            return prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(phase))
        if entity == "BattleGroundAvatar" and name in ("changeFallPhase", "changeGlidePhase") and args:
            phase = struct.unpack("<b", args[:1])[0]
            prop = "fallPhase" if name == "changeFallPhase" else "glidePhase"
            if prop == "fallPhase":
                self.fall_phase = phase
            log("      [BATTLE] %s(%d) -> %s %d" % (name, phase, prop, phase))
            return prop_update("BattleGroundAvatar", AVATAR_ID, prop, i8(phase))
        if entity == "BattleGroundAvatar" and name == "doPutGun" and args:
            return prop_update("BattleGroundAvatar", AVATAR_ID, "isPutgun", args[:1])
        if entity == "BattleGroundAvatar" and name in ("requestLeaveSpaceBeforeWin", "suicideFromClient"):
            self.leave = True
            return b""
        if entity == "BattleGroundSpace" and name == "openElement":
            elem, state = struct.unpack("<ib", args[:5])
            self.doors[elem] = state
            return client_call("BattleGroundSpace", "onElementOpen", SPACE_ID, args[:5])
        if entity == "BattleGroundSpace" and name == "closeElement":
            elem = struct.unpack("<i", args[:4])[0]
            self.doors[elem] = 0
            return client_call("BattleGroundSpace", "onElementClose", SPACE_ID, args[:4])
        if entity == "DtsProp" and name == "tryPickUp" and eid in self.props:
            prop_id, amount = self.props.pop(eid)
            log("      [BATTLE] pickup prop %s x%s (entity %s, %s)" % (prop_id, amount, eid, prop_type(prop_id)))
            if prop_type(prop_id) == "Gun":
                slot = next((s for s in (1, 2) if not self.gun_slots[s]), 1)
                self.gun_slots[slot] = prop_id
                return (leave_aoi(eid)
                        + prop_update("BattleGroundAvatar", AVATAR_ID, "dtsWeapon%d" % slot, weapon_item(prop_id))
                        + prop_update("BattleGroundAvatar", AVATAR_ID, "dtsCurWeapon", i32(slot))
                        + client_call("BattleGroundAvatar", "onWearDtsWeapon", AVATAR_ID, i32(slot))
                        + client_call("BattleGroundAvatar", "onPickUpPropEntity", AVATAR_ID))
            import pickle
            info = bwdefs.blob(pickle.dumps({"ex_tm": 0}, protocol=2))
            item = bwdefs.blob(os.urandom(16)) + i32(amount) + info + i32(0)
            add = i32(prop_id) + struct.pack("<I", 1) + item + i8(0) + i32(0)
            return (leave_aoi(eid) + client_call("BattleGroundAvatar", "onAddDtsItem", AVATAR_ID, add)
                    + client_call("BattleGroundAvatar", "onPickUpPropEntity", AVATAR_ID))
        return b""


def indexed_call(index, eid, args=b"", n_total=769):
    """Entity message for a global message index (method or property) using the same
    extended-index scheme as client_call: direct below `eff`, else msg 0x80 | (eff + (k >> 8)) + sub byte."""
    eff = 62 - (n_total + 192) // 255
    if index < eff:
        return _var16(0x80 | index, struct.pack("<I", eid) + args)
    k = index - eff
    return _var16(0x80 | (eff + (k >> 8)), struct.pack("<I", eid) + bytes([k & 0xFF]) + args)


# ---- property updates (docs/ENTITY_PROPERTY_UPDATE_FORMAT.md) --------------------------------
_PF = {'CELL_PRIVATE': 0, 'PRIVATE': 0, 'CELL_PUBLIC': 1, 'CELL': 1, 'GHOSTED': 1, 'OTHER_CLIENTS': 3, 'OTHER_CLIENT': 3,
       'OWN_CLIENT': 4, 'BASE': 8, 'BASE_AND_CLIENT': 0xC, 'CELL_PUBLIC_AND_OWN': 5, 'GHOSTED_AND_OWN': 5,
       'CELL_AND_OWN': 5, 'ALL_CLIENTS': 7, 'ALL_CLIENT': 7, 'EDITOR_ONLY': 0x40, '': 0}


def update_prop_list(entity):
    """The client's property index list for updates: parse order, first position / last definition,
    flags & 6 (includes BASE_AND_CLIENT). BattleGroundAvatar = 495 entries."""
    key = ("upd", entity)
    if key not in _CACHE:
        order, last = [], {}
        for p in defs().properties(entity):
            if p[0] not in last:
                order.append(p[0])
            last[p[0]] = p
        _CACHE[key] = [last[n][:3] for n in order if _PF.get(last[n][2], 0) & 6]
    return _CACHE[key]


def prop_update(entity, eid, name, value):
    """Server -> client change of one whole property: id 0xC0|idx (var8) for idx <= 60, else 0xFD (var16)
    + entity id + 2-byte bit path (index, more-bit 0) + value."""
    lst = update_prop_list(entity)
    idx = [p[0] for p in lst].index(name)
    if idx <= 60:
        payload = struct.pack("<I", eid) + value
        return bytes([0xC0 | idx, len(payload)]) + payload
    nbits = (len(lst) - 1).bit_length()
    path = ((idx << 1) << (16 - nbits - 1)).to_bytes(2, "big")
    return _var16(0xFD, struct.pack("<I", eid) + path + value)


def update_property(entity, name, value, eid=None):
    """RO-059 encoder: property update for entity type ``entity``.
    ``value`` is the already-encoded property bytes. ``eid`` defaults to AVATAR_ID for
    BattleGroundAvatar and SPACE_ID for BattleGroundSpace; pass eid for Plane/DtsProp/Robot."""
    if eid is None:
        if entity == "BattleGroundAvatar":
            eid = AVATAR_ID
        elif entity == "BattleGroundSpace":
            eid = SPACE_ID
        elif entity == "Plane":
            eid = PLANE_ID
        else:
            raise TypeError("update_property requires eid for entity type %r" % entity)
    return prop_update(entity, eid, name, value)


def weapon_item(weapon_id):
    """BATTLE_GROUND_WEAPON_ITEM with weaponID set, other fields default."""
    return struct.pack("<I", weapon_id) + bwdefs.encode_default(defs().resolve("BATTLE_GROUND_WEAPON_ITEM"), None)[4:]

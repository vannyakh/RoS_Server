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
# Plane route across map 700 at the drop height (inside CIRCLE_BOUND_BOX (-22430, -20648) .. (8451, 10375)),
# passing over FLIGHT_START. FLIGHT_ROUTE="x1,z1,x2,z2" overrides. Speed in map units per second.
FLIGHT_ROUTE = tuple(float(v) for v in os.environ.get("FLIGHT_ROUTE", "-16000,-14000,7000,6000").split(","))
FLIGHT_SPEED = float(os.environ.get("FLIGHT_SPEED", "500"))
FLIGHT_POS_EVERY = 0.2        # s between detailedPosition updates (the client's AvatarFilter interpolates)
# planeID in the same bundle as the plane's createEntity does not attach the player (getOnPlane needs the
# loaded plane): set it a few seconds later. Verified 2026-11-26: plane at +0 s, planeID at +3 s -> on the
# plane (camera behind the aircraft, "Onboard", Jump button).
_PLANE = int(os.environ.get("PLANE_ENTITY_ID", "20002"))
FLIGHT_STEPS = (
    (0.0, ("flight",)),
    (1.0, ("leave %d" % int(os.environ.get("SPACE_ENTITY_ID", "20001")), "spaces 2 {stage}")),
    (3.0, ("setp planeID 0", "setp planeID %d" % _PLANE, "setp leftPlayerNumOnPlane 1", "setp fallPhase 2")),
)
# The Jump button releases the player (Match.handle requestGetOffPlane: planeID 0, FLIGHT_START, CAN_FALL).
# FLIGHT_AUTO_RELEASE=on adds the old timed release instead, 2.5 s after boarding.
if os.environ.get("FLIGHT_AUTO_RELEASE", "off") == "on":
    FLIGHT_STEPS = FLIGHT_STEPS + ((5.5, ("setp planeID 0", "tp %s %s %s" % FLIGHT_START, "setp fallPhase 2")),)


# ---- test trigger ---------------------------------------------------------------------------
SPACE_ID = int(os.environ.get("SPACE_ENTITY_ID", "20001"))
PLANE_ID = int(os.environ.get("PLANE_ENTITY_ID", "20002"))


def debug_command(line, map_id=700, match=None):
    """One line of server/trigger_battle.txt -> bytes to send (experiments on a live match).
      space0          BattleGroundSpace with no properties
      space           BattleGroundSpace with mapID and a circle at the player's area
      leave <eid>     leaveAoI
      raw <hex>       raw ClientInterface bytes"""
    _adopt(match)
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
    if cmd == "flight":                 # flight: Plane at the start of FLIGHT_ROUTE, then flown by the match timeline
        x1, z1, x2, z2 = FLIGHT_ROUTE
        y = FLIGHT_START[1]
        path = [(x1, y, z1), (x2, y, z2)]
        hp = b""
        if match is not None:
            import time
            match.flight = {"start": path[0], "end": path[1], "t0": time.time(), "last": 0.0, "done": False}
            match.hp = MAX_HP
            hp = hp_messages(MAX_HP, MAX_HP)
        return hp + create_entity(PLANE_ID, "Plane", pos=path[0], values={
            "mapID": i32(map_id), "moveSpeed": f32(FLIGHT_SPEED), "inJumpArea": i8(1), "mode": i32(1),
            "movePath": arr_vec3(path)})
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
    if cmd == "board":                  # board [x z]: zone + plane over (x, z), put the player on it
        x, z = (float(v) for v in (parts[1:3] if len(parts) >= 3 else (0.0, 0.0)))
        return board_messages(map_id, (x, z))
    if cmd == "setp8":                  # setp8 <name> <int8>: own player INT8 property
        return prop_update("BattleGroundAvatar", AVATAR_ID, parts[1], i8(int(parts[2])))
    if cmd == "dpos":                   # dpos <eid> <x> <y> <z> [yaw]: detailedPosition (0x58, fixed 30) test
        eid = int(parts[1])
        x, y, z = (float(v) for v in parts[2:5])
        yaw = float(parts[5]) if len(parts) > 5 else 0.0
        return detailed_position(eid, (x, y, z), (0.0, 0.0, yaw))
    if cmd == "zone" and match is not None:     # zone [time scale] [away]: (re)start the safe zone now
        import time
        return match.zone_start(time.time(), float(parts[1]) if len(parts) > 1 else None, away="away" in parts)
    if cmd == "result" and match is not None:   # result <rank> [total]: result screen now (once per match)
        match.finished = False
        return match.finish(int(parts[1]) if len(parts) > 1 else 1, total=int(parts[2]) if len(parts) > 2 else None)
    if cmd == "chute" and match is not None:    # chute client|server: who drives CAN_OPEN / OPENED (07.10)
        match.chute_client = parts[1:2] == ["client"]
        return b""
    if cmd == "hp" and match is not None:       # hp <n>: set the own hp (zone-death tests without waiting)
        match.hp = int(parts[1])
        return hp_messages(match.hp)
    if cmd == "die" and match is not None:      # die: hp 0, battleState Died, result screen (last place)
        match.hp, match.finished, match.death_cause = 0, False, "trigger"
        return (hp_messages(0) + prop_update("BattleGroundAvatar", AVATAR_ID, "battleState", i8(STATE_DIED))
                + match.finish(RESULT_TOTAL))
    if cmd == "drop" and match is not None:     # drop: repeat the Jump release in the current match (tests)
        match.jump_y, match.fall_phase, match.landed, match.fall_started, match.chute_open = FLIGHT_START[1], FALL_CAN, False, False, False
        match.max_y, match.still_since = None, None
        return (prop_update("BattleGroundAvatar", AVATAR_ID, "planeID", i32(0))
                + forced_position(AVATAR_ID, FLIGHT_START)
                + prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_CAN)))
    if cmd == "fpos":                   # fpos <x> <y> <z>: forcedPosition of the own player
        return forced_position(AVATAR_ID, tuple(float(v) for v in parts[1:4]))
    if cmd == "sprop":                  # sprop <name> <int32>: BattleGroundSpace INT32 property
        return prop_update("BattleGroundSpace", SPACE_ID, parts[1], i32(int(parts[2])))
    if cmd in ("car", "airdrop", "geton", "getoff") and match is not None: return __import__("battle_world").hook_debug(match, parts)   # lane 5
    if cmd == "leave":
        return leave_aoi(int(parts[1]))
    if cmd == "raw":
        return bytes.fromhex("".join(parts[1:]))
    raise ValueError(f"unknown battle trigger {cmd!r}")


FALL_NORMAL, FALL_BEFORE, FALL_CAN, FALL_BEFORE_OPEN, FALL_CAN_OPEN, FALL_OPENED = range(6)   # const.FallPhase
STATE_NORMAL, STATE_PARACHUTE = 0, 4                                   # const.PlayerState
GS_READY, GS_PREPARE, GS_BEFORE_FIGHT, GS_FIGHT, GS_END = range(5)     # BattleGroundGameStatusEnum
PLANE_HEIGHT = float(os.environ.get("PLANE_HEIGHT", "500"))
PLANE_SPEED = float(os.environ.get("PLANE_SPEED", "60"))


def plane_path(center, half=1800.0):
    """Straight flight line through `center` (x, z) along the map diagonal."""
    x, z = center
    return [(x - half, PLANE_HEIGHT, z - half), (x + half, PLANE_HEIGHT, z + half)]


CELL_SPACE_ID = int(os.environ.get("CCP_SPACE", "1"))


def forced_position(eid, pos, direction=(0.0, 0.0, 0.0), vehicle=0):
    """ClientInterface::forcedPosition(id, spaceID, vehicleID, position, direction): moves the own
    player (BigWorld 2.x layout, 4+4+4+12+12 = 36 bytes)."""
    return bytes([MSG_FORCED_POSITION]) + struct.pack("<III3f3f", eid, CELL_SPACE_ID, vehicle, *pos, *direction)


# ---- safe zone (BattleGroundSpace circles) -----------------------------------------------------------
# Map 700 (maps_utils.getBattleGroundParamData(700), read with client/frida/payloads/circle_param.py):
# initial blue circle (-7507, -4674) r 32000; per stage (PREPARE_TIME wait, SCALE_TIME shrink, RADIUS).
# The client animates the blue circle toward each new blueCircleRadius / blueCircleCenter value
# (BattleGroundSpace.updateBlueCircle, 0.05 s steps), so the server sends the interpolated circle
# about once a second while it shrinks. updateCircleRestTime(INT32) drives the HUD zone timer.
ZONE_INIT = ((-7507.0, -4674.0), 32000)
ZONE_STAGES = ((270, 180, 16000), (150, 150, 10000), (120, 120, 6000), (120, 80, 3000),
               (90, 60, 1500), (90, 60, 750), (90, 60, 300), (120, 120, 0))
ZONE_TIME_SCALE = float(os.environ.get("ZONE_TIME_SCALE", "1.0"))    # < 1 speeds the zone up (tests)
# Damage outside the blue circle per stage: (DAMAGE hp, every INTERVAL s) from CIRCLE_PARAM.
ZONE_DAMAGE = ((1, 5.0), (1, 3.3), (1, 2.0), (1, 1.0), (2, 1.0), (3, 1.0), (5, 1.0), (7, 1.0))
MAX_HP = int(os.environ.get("BATTLE_MAX_HP", "100"))
STATE_DIED = 2                                                      # const.PlayerState.Died

# ---- match result (death / win screen) ------------------------------------------------------------
# BattleGroundAvatar.onBattleGroundDie(PYTHON killerInfo) -> death UI (iBattleGround._delayShowResult).
# BattleGroundAvatar.onBattleGroundResult(INT32 gameType, INT8 teamSize, INT32 rank, INT32 total,
# INT32 bannerID, PY_DICT results, PY_DICT killerInfo) -> iBattleGround._delayShowResult (2 s) ->
# ui.UIBattlegroundsResult. Read with client/frida/payloads/result_dis*.py, result_ui_dis.py, result_consts.py.
# results = {gid: row}; the screen reads its own row by the avatar's gid: gps (timeGP, killGP, rankGP,
# healGP, moveGP, collectGP), dailyFirstGameReward (amount, MallCurrencyType), randomGP, GPMul, exp, and
# for every member nickname, kill, score, moveDis, collectCount, healTeammate. modeMark is
# teamSizeToModeName[teamSize] + '-' + const.DTS_TYPE_NAME[gameType] (a missing key breaks the screen).
# Exit / Next send base.requestLeaveDynamicSpace, which the gateway already answers with the lobby.
RESULT_GAME_TYPE = int(os.environ.get("RESULT_GAME_TYPE", "1"))     # const.GameEnterType.MATCHING
RESULT_TOTAL = int(os.environ.get("RESULT_TOTAL", "100"))           # players in the match (HUD "100 LEFT")
BANNER_WIN_SINGLE, BANNER_LOSE_SINGLE_TOP10, BANNER_LOSE = 7, 9, 10  # const.BattleGroundBannerType


def die_call(killer_info=None):
    """BattleGroundAvatar.onBattleGroundDie(PYTHON killerInfo) before the result screen on elimination."""
    import pickle
    return client_call("BattleGroundAvatar", "onBattleGroundDie", AVATAR_ID,
                       bwdefs.blob(pickle.dumps(killer_info if killer_info is not None else {}, protocol=2)))


def result_call(rank, total, gid, nickname, kills=0, collected=0, move=0):
    """onBattleGroundResult for a solo player (no GP or exp is granted, so the reward rows are 0)."""
    import pickle
    banner = BANNER_WIN_SINGLE if rank == 1 else BANNER_LOSE_SINGLE_TOP10 if rank <= 10 else BANNER_LOSE
    row = {"gps": (0, 0, 0, 0, 0, 0), "dailyFirstGameReward": (0, 1), "randomGP": 0, "GPMul": 1, "exp": 0,
           "nickname": nickname, "name": nickname, "kill": kills, "score": 0, "moveDis": move,
           "collectCount": collected, "healTeammate": 0, "nationalFlag": ""}
    args = (i32(RESULT_GAME_TYPE) + i8(1) + i32(rank) + i32(total) + i32(banner)
            + bwdefs.blob(pickle.dumps({gid: row}, protocol=2)) + bwdefs.blob(pickle.dumps({}, protocol=2)))
    if os.environ.get("RESULT_CM_INDEX"):         # override if the +3 client index offset is wrong here
        return indexed_call(int(os.environ["RESULT_CM_INDEX"]), AVATAR_ID, args,
                            n_total=client_methods("BattleGroundAvatar")[1])
    return client_call("BattleGroundAvatar", "onBattleGroundResult", AVATAR_ID, args)


def hp_messages(hp, max_hp=None):
    """hp (and maxHp) of the own player; the HUD health bar reads them (both were 0 before)."""
    out = b""
    if max_hp is not None:
        out += prop_update("BattleGroundAvatar", AVATAR_ID, "maxHp", i32(max_hp))
    return (out + prop_update("BattleGroundAvatar", AVATAR_ID, "hp", i32(hp))
            + prop_update("BattleGroundAvatar", AVATAR_ID, "actualHP", i32(hp)))
ZONE_AUTO = os.environ.get("ZONE_AUTO", "on") != "off"               # start the zone after the landing


def _toward(center, target, limit):
    """Point from `center` toward `target`, at most `limit` away (keeps the white circle inside the blue)."""
    import math
    dx, dz = target[0] - center[0], target[1] - center[1]
    d = math.hypot(dx, dz)
    if d <= limit or d == 0:
        return target
    return (center[0] + dx * limit / d, center[1] + dz * limit / d)


AUTO_BOARD = os.environ.get("AUTO_BOARD", "off") == "on"   # alternative to FLIGHT_STEPS
BOARD_DELAY = float(os.environ.get("BOARD_DELAY", "3"))        # s between plane createEntity and planeID
PARACHUTE_HEIGHT = float(os.environ.get("PARACHUTE_HEIGHT", "150"))   # m above ground: open parachute
LAND_HEIGHT = float(os.environ.get("LAND_HEIGHT", "3"))                # m above ground: landed
MSG_AVATAR_UPDATE = 2              # client -> server position report: x, y, z floats first


MSG_DETAILED_POSITION = 0x58       # message_map seq 109 - 21, fixed 30 bytes


def detailed_position(eid, pos, direction=(0.0, 0.0, 0.0)):
    """ClientInterface::detailedPosition for a non-player entity. 30 bytes: id, position 3f, direction 3f
    (= 28, the BigWorld 2.x layout) + 2 bytes whose meaning is unknown (sent as 0). DPOS_TAIL=front moves
    the 2 bytes after the id instead (alternative layout)."""
    if os.environ.get("DPOS_TAIL", "end") == "front":
        return bytes([MSG_DETAILED_POSITION]) + struct.pack("<IH3f3f", eid, 0, *pos, *direction)
    return bytes([MSG_DETAILED_POSITION]) + struct.pack("<I3f3fH", eid, *pos, *direction, 0)


def board_entities(map_id, center, ground_y):
    """Zone in BEFORE_FIGHT + a Plane parked over (x, z) at ground + PLANE_HEIGHT. planeID must be set
    a moment later: PlayerAvatar.set_planeID needs BigWorld.entities[planeID] to exist and be loaded,
    else getOnPlane does not run (seen live 2026-11-21)."""
    x, z = center
    y = ground_y + PLANE_HEIGHT
    path = [(x, y, z), (x + 1.0, y, z + 1.0)]       # parked: plane movement is not streamed yet
    space = create_entity(SPACE_ID, "BattleGroundSpace", values={
        "mapID": i32(map_id), "gameStatus": i32(GS_BEFORE_FIGHT), "aliveNum": i32(1), "circleStage": i32(0),
        "whiteCircleCenter": vec2(x, z), "whiteCircleRadius": i32(1500),
        "blueCircleCenter": vec2(x, z), "blueCircleRadius": i32(3000),
        "blueCircleStartCenter": vec2(x, z), "blueCircleStartRadius": i32(3000),
        "planeEntityIDs": arr_i32([PLANE_ID])})
    plane = create_entity(PLANE_ID, "Plane", pos=path[0], values={
        "mapID": i32(map_id), "moveSpeed": f32(PLANE_SPEED), "inJumpArea": i8(1), "mode": i32(1),
        "movePath": arr_vec3(path)})
    return space + plane, path[0]


def board_player():
    return (prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_CAN))
            + prop_update("BattleGroundAvatar", AVATAR_ID, "leftPlayerNumOnPlane", i32(1))
            + prop_update("BattleGroundAvatar", AVATAR_ID, "planeID", i32(PLANE_ID)))


def board_messages(map_id, center):
    """Zone (BattleGroundSpace) + Plane entity, then put the player on the plane.
    Client: PlayerAvatar.set_planeID(id) -> BigWorld.entities[id] -> getOnPlane (parents the player
    to the plane, opens UIBattlegroundsFall); set_leftPlayerNumOnPlane updates that panel while
    fallPhase is BEFORE_FALL / CAN_FALL."""
    x, z = center
    path = plane_path(center)
    space = create_entity(SPACE_ID, "BattleGroundSpace", values={
        "mapID": i32(map_id), "gameStatus": i32(1), "aliveNum": i32(1), "circleStage": i32(0),
        "whiteCircleCenter": vec2(x, z), "whiteCircleRadius": i32(1500),
        "blueCircleCenter": vec2(x, z), "blueCircleRadius": i32(3000),
        "blueCircleStartCenter": vec2(x, z), "blueCircleStartRadius": i32(3000),
        "planeEntityIDs": arr_i32([PLANE_ID])})
    plane = create_entity(PLANE_ID, "Plane", pos=path[0], values={
        "mapID": i32(map_id), "moveSpeed": f32(PLANE_SPEED), "inJumpArea": i8(1), "mode": i32(0),
        "movePath": arr_vec3(path)})
    return (space + plane
            + prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_CAN))
            + prop_update("BattleGroundAvatar", AVATAR_ID, "leftPlayerNumOnPlane", i32(1))
            + prop_update("BattleGroundAvatar", AVATAR_ID, "planeID", i32(PLANE_ID)))


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
    if 26000 <= eid < 27000: return __import__("battle_world").hook_entity_type(eid) or "BattleGroundAvatar"   # lane 5
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
    # 2026-11-21: requestGetOffPlane (77) and verifyClientValue (150) arrive unshifted, so the shift
    # starts in 151..207; 180 until measured.
    if entity == "BattleGroundAvatar" and k >= int(os.environ.get("EXPOSED_SHIFT_FROM", "180")):
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



def _adopt(match):
    """Move a match object created before a hot reload of this module onto the current Match class,
    so methods added or changed since then are found (self.zone_start etc.)."""
    if match is not None and type(match) is not Match and type(match).__name__ == "Match":
        match.__class__ = Match
    return match


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
        self.on_plane = False
        self.stage = "ground"            # ground -> spawned -> plane -> falling -> parachute -> landed
        self.stage_time = 0.0
        self.ground_y = 0.0
        self.plane_pos = None
        self.map_id = int(os.environ.get("BATTLE_MAP", "700"))
        import time
        self.t_start = time.time()       # survival time (match_results.survival_seconds)

    def _set_stage(self, stage, log):
        import time
        log("      [BATTLE] stage %s -> %s (pos %s)" % (self.stage, stage, tuple(round(v, 1) for v in self.pos) if self.pos else None))
        self.stage, self.stage_time = stage, time.time()

    def plane_position(self, now):
        """(position, yaw, finished) of the plane on its route at time `now`."""
        import math
        fl = self.flight
        (x1, y, z1), (x2, _y, z2) = fl["start"], fl["end"]
        length = math.hypot(x2 - x1, z2 - z1)
        k = min((now - fl["t0"]) * FLIGHT_SPEED / max(length, 1.0), 1.0)
        return (x1 + (x2 - x1) * k, y, z1 + (z2 - z1) * k), math.atan2(x2 - x1, z2 - z1), k >= 1.0

    def release_from_plane(self, start, log=print):
        """Off the plane at `start`: planeID 0, forcedPosition, CAN_FALL; the fall phases follow
        (_parachute_phase) and on_position lands the player."""
        self.on_plane = False
        if getattr(self, "stage", None) in ("plane", "spawned"):
            self._set_stage("falling", log)
        self.jump_y, self.fall_phase, self.fall_started, self.chute_open = start[1], FALL_CAN, False, False
        log("      [BATTLE] jump: off the plane at (%.0f, %.0f, %.0f) -> CAN_FALL" % tuple(start))
        return (prop_update("BattleGroundAvatar", AVATAR_ID, "planeID", i32(0))
                + forced_position(AVATAR_ID, tuple(start))
                + prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_CAN)))

    def flight_tick(self, now, log=print):
        """Fly the plane along its route (detailedPosition every FLIGHT_POS_EVERY s); at the end of the
        route a player still aboard is released as if the Jump button was pressed."""
        fl = getattr(self, "flight", None)
        if not fl or fl["done"] or now - fl["last"] < FLIGHT_POS_EVERY:
            return b""
        fl["last"] = now
        pos, yaw, finished = self.plane_position(now)
        out = detailed_position(PLANE_ID, pos, (0.0, 0.0, yaw))
        if finished:
            fl["done"] = True
            log("      [BATTLE] plane reached the end of its route at (%.0f, %.0f, %.0f)" % pos)
            if getattr(self, "jump_y", None) is None:          # still aboard: forced jump
                out += self.release_from_plane(pos, log)
        return out

    def zone_start(self, now, scale=None, log=print, away=False):
        """Stage 1: FIGHT, the initial blue circle and the first white circle (toward the player, or to the
        far side of the blue circle with away=True, for damage tests)."""
        self.zone = {"stage": 0, "phase": "wait", "t0": now, "scale": ZONE_TIME_SCALE if scale is None else scale,
                     "blue": ZONE_INIT, "last_sent": 0.0, "away": away, "last_damage": now, "poison": False}
        log("      [BATTLE] zone start (time scale %.2f%s)" % (self.zone["scale"], ", away" if away else ""))
        out = b""
        if not getattr(self, "hp", None):
            self.hp = MAX_HP
            out += hp_messages(MAX_HP, MAX_HP)
        return (out + prop_update("BattleGroundSpace", SPACE_ID, "gameStatus", i32(GS_FIGHT))
                + self._zone_blue(ZONE_INIT) + self._zone_next_white(now, log))

    def _zone_blue(self, circle):
        (x, z), r = circle
        return (prop_update("BattleGroundSpace", SPACE_ID, "blueCircleCenter", vec2(x, z))
                + prop_update("BattleGroundSpace", SPACE_ID, "blueCircleRadius", i32(int(r))))

    def _zone_next_white(self, now, log):
        zs = self.zone
        wait, _scale_t, radius = ZONE_STAGES[zs["stage"]]
        (bx, bz), br = zs["blue"]
        player = (self.pos[0], self.pos[2]) if getattr(self, "pos", None) else (bx, bz)
        if zs.get("away"):                                   # opposite side of the blue circle
            player = (2 * bx - player[0], 2 * bz - player[1])
        cx, cz = _toward((bx, bz), player, max(br - radius, 0))
        zs.update(white=((cx, cz), radius), phase="wait", t0=now)
        secs = int(wait * zs["scale"])
        log("      [BATTLE] zone stage %d: white (%.0f, %.0f) r %d, shrink in %d s" % (zs["stage"] + 1, cx, cz, radius, secs))
        return (prop_update("BattleGroundSpace", SPACE_ID, "circleStage", i32(zs["stage"] + 1))
                + prop_update("BattleGroundSpace", SPACE_ID, "whiteCircleCenter", vec2(cx, cz))
                + prop_update("BattleGroundSpace", SPACE_ID, "whiteCircleRadius", i32(radius))
                + client_call("BattleGroundSpace", "updateCircleRestTime", SPACE_ID, i32(secs)))

    def zone_tick(self, now, log=print):
        """Advance the zone: wait -> shrink (blue interpolated toward white, ~1 s steps) -> next stage."""
        zs = getattr(self, "zone", None)
        if not zs:
            return b""
        dmg = self._zone_damage(now, log)
        if zs.get("done"):
            return dmg
        rest = self._zone_shrink(now, log)
        return dmg + rest

    def _zone_damage(self, now, log):
        """Outside the blue circle: -DAMAGE hp every INTERVAL s (stage values), isInPoisonArea on the edge
        crossing, showPoisonEffect on each hit; at 0 hp battleState Died."""
        import math
        zs = self.zone
        if not getattr(self, "pos", None) or getattr(self, "hp", 0) <= 0:
            return b""
        (bx, bz), br = zs["blue"]
        outside = math.hypot(self.pos[0] - bx, self.pos[2] - bz) > br
        out = b""
        if outside != zs["poison"]:
            zs["poison"] = outside
            log("      [BATTLE] %s the safe zone (hp %d)" % ("left" if outside else "back in", self.hp))
            out += prop_update("BattleGroundAvatar", AVATAR_ID, "isInPoisonArea", i8(1 if outside else 0))
        amount, every = ZONE_DAMAGE[min(zs["stage"], len(ZONE_DAMAGE) - 1)]
        if not outside or now - zs["last_damage"] < every:
            return out
        zs["last_damage"] = now
        self.hp = max(self.hp - amount, 0)
        out += hp_messages(self.hp) + client_call("BattleGroundAvatar", "showPoisonEffect", AVATAR_ID)
        if self.hp == 0:
            log("      [BATTLE] killed by the zone")
            out += prop_update("BattleGroundAvatar", AVATAR_ID, "battleState", i8(STATE_DIED))
            out += self.finish(RESULT_TOTAL, log)       # alone in the match: last place
        return out

    def finish(self, rank, log=print, total=None):
        """Result screen (once per match). Its Exit button returns the player to the lobby."""
        if getattr(self, "finished", False):
            return b""
        self.finished = True
        total = total or RESULT_TOTAL
        import account_link                  # the avatar's gid (ros_server sends account_link.current_gid())
        gid = account_link.current_gid()
        linked = account_link.current() or {}
        name = linked.get("nickname") or os.environ.get("TEST_ACCOUNT_NAME") or "Player"
        log("      [BATTLE] match result: rank %d / %d (gid %s)" % (rank, total, gid))
        import match_results
        match_results.save(self, gid, name, rank, total, won=rank == 1, log=log)
        out = die_call() if getattr(self, "hp", 0) <= 0 else b""
        return out + result_call(rank, total, gid, name, collected=getattr(self, "collected", 0))

    def _zone_shrink(self, now, log):
        zs = self.zone
        wait, scale_t, _radius = ZONE_STAGES[zs["stage"]]
        if zs["phase"] == "wait":
            if now - zs["t0"] < wait * zs["scale"]:
                return b""
            zs.update(phase="shrink", t0=now, start=zs["blue"])
            secs = int(scale_t * zs["scale"])
            log("      [BATTLE] zone stage %d shrinking over %d s" % (zs["stage"] + 1, secs))
            (sx, sz), sr = zs["start"]
            return (prop_update("BattleGroundSpace", SPACE_ID, "blueCircleStartCenter", vec2(sx, sz))
                    + prop_update("BattleGroundSpace", SPACE_ID, "blueCircleStartRadius", i32(int(sr)))
                    + client_call("BattleGroundSpace", "updateCircleRestTime", SPACE_ID, i32(secs)))
        if now - zs.get("last_sent", 0) < 1.0:
            return b""
        zs["last_sent"] = now
        k = min((now - zs["t0"]) / max(scale_t * zs["scale"], 0.1), 1.0)
        (sx, sz), sr = zs["start"]
        (wx, wz), wr = zs["white"]
        zs["blue"] = ((sx + (wx - sx) * k, sz + (wz - sz) * k), sr + (wr - sr) * k)
        out = self._zone_blue(zs["blue"])
        if k >= 1.0:
            if zs["stage"] + 1 >= len(ZONE_STAGES):
                zs["done"] = True
                log("      [BATTLE] zone closed")
                if getattr(self, "hp", 0) > 0:             # survived the last circle: win
                    out += self.finish(1, log)
                return out
            zs["stage"] += 1
            out += self._zone_next_white(now, log)
        return out

    def on_message(self, msgid, payload, log=print):
        """Match timeline driven by client traffic: auto-boarding, then parachute / landing by height
        (freefall ignores terrain on this client, so the server must change fallPhase)."""
        _adopt(self)
        import time
        fl = self.flight_tick(time.time(), log)
        if fl:
            return fl
        zone = b""
        if getattr(self, "zone", None):
            zone = self.zone_tick(time.time(), log)
        elif ZONE_AUTO and getattr(self, "landed", False):
            zone = self.zone_start(time.time(), log=log)
        if zone:
            return zone
        if (wo := __import__("battle_world").hook_message(self, msgid, payload, log)): return wo   # lane 5: vehicles, airdrop
        if msgid == MSG_AVATAR_UPDATE and len(payload) >= 12:
            self.pos = struct.unpack_from("<3f", payload)
        if not getattr(self, "stage", None):
            self.stage, self.stage_time, self.pos = "ground", 0.0, getattr(self, "pos", None)
        if 0x80 <= msgid <= 0xBF and not getattr(self, "map_up", 0):
            self.map_up = time.time()        # first cell call = HUD up, player standing on the map
        if self.pos is None:
            return b""
        x, y, z = self.pos
        # Spawn the plane only once the player stands on the terrain: the avatar is created at exactly
        # (0, 0, 0) and the first different report is the client placing it on the ground. A plane
        # entering the world during the loading screen runs getOnPlane -> enterObserverMode too early
        # (script error, then the client hung - ANR - on 2026-11-21).
        settled = abs(x) + abs(y) + abs(z) > 0.01
        if (self.stage == "ground" and AUTO_BOARD and settled and getattr(self, "map_up", 0)
                and time.time() - self.map_up >= 2.0):
            self.ground_y = y
            data, self.plane_pos = board_entities(self.map_id, (x, z), y)
            self._set_stage("spawned", log)
            return data
        if self.stage == "spawned" and time.time() - self.stage_time >= BOARD_DELAY:
            self._set_stage("plane", log)
            self.board_try = time.time()
            return board_player()
        # set_planeID during the loading screen does not attach the player (getOnPlane needs the loaded
        # plane model): while position reports still show the ground, re-send planeID every 5 s.
        # The first reports can be the raw spawn point (0, 0, 0) before the player settles on the
        # terrain (ground was y -468 at map 700's spawn), so keep the ground height current until the
        # player is up on the plane.
        plane_y = self.plane_pos[1] if getattr(self, "plane_pos", None) else self.ground_y + PLANE_HEIGHT
        if self.stage in ("spawned", "plane") and y < plane_y - 100:
            self.ground_y = y
        if (self.stage == "plane" and y < plane_y - 100
                and time.time() - getattr(self, "board_try", 0) >= 5.0):
            self.board_try = time.time()
            log("      [BATTLE] not on the plane yet (y %.1f): re-sending planeID" % y)
            return prop_update("BattleGroundAvatar", AVATAR_ID, "planeID", i32(0)) + board_player()
        if self.stage == "falling" and y <= self.ground_y + PARACHUTE_HEIGHT:
            self._set_stage("parachute", log)
            if getattr(self, "chute_client", False) or getattr(self, "chute_open", False):
                return b""                   # the client opened it (button or its own height check)
            return (prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_CAN_OPEN))
                    + prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_OPENED)))
        if self.stage == "parachute" and y <= self.ground_y + LAND_HEIGHT:
            self._set_stage("landed", log)
            # back to the normal state a little above the ground; normal physics collides with the
            # real terrain, so uneven ground still ends with the player standing on it
            return (prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(FALL_NORMAL))
                    + prop_update("BattleGroundAvatar", AVATAR_ID, "battleState", i8(STATE_NORMAL))
                    + prop_update("BattleGroundAvatar", AVATAR_ID, "hasLanded", i8(1))
                    + forced_position(AVATAR_ID, (x, max(y, self.ground_y) + 2.0, z))
                    + prop_update("BattleGroundSpace", SPACE_ID, "gameStatus", i32(GS_FIGHT)))
        return b""

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
        _adopt(self)
        if len(payload) < 20 or self.landed:
            return b""
        x, y, z = struct.unpack_from("<3f", payload, 8)
        last = self.pos
        self.pos = (x, y, z)
        self.max_y = y if self.max_y is None else max(self.max_y, y)
        chute = self._parachute_phase(y, log)
        if chute:
            return chute
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
                + prop_update("BattleGroundAvatar", AVATAR_ID, "flightStage", i32(2))
                + prop_update("BattleGroundAvatar", AVATAR_ID, "battleState", i8(STATE_NORMAL))
                + prop_update("BattleGroundAvatar", AVATAR_ID, "hasLanded", i8(1)))

    def _parachute_phase(self, y, log):
        """Server-driven fall phases after the Jump button (the client does not always send fall()).
        Heights are fractions of the drop from the jump point to FLIGHT_GROUND (the measured terrain under
        FLIGHT_START), since the map's unit is not confirmed:
          falling        -> fallPhase BEFORE_OPEN_PARACHUTE + battleState Parachute (skydive HUD)
          CHUTE_BUTTON   -> CAN_OPEN_PARACHUTE (UIBattlegroundsFall shows the parachute button; the button
                            runs the client's own state machine, TRIGGER_OPEN_PARACHUTE)
          CHUTE_AUTO     -> PARACHUTE_OPENED if the player has not opened it."""
        jump_y = getattr(self, "jump_y", None)
        if jump_y is None or getattr(self, "chute_open", False):
            return b""
        ground = float(os.environ.get("FLIGHT_GROUND", "-677"))
        drop = max(jump_y - ground, 1.0)
        done = (jump_y - y) / drop                    # 0 at the jump point, 1 on the ground
        # Reports sent before the forcedPosition arrives still carry the old position (seen: a stale
        # -677 stepped all phases at once). Start once a report is near the jump height.
        if not getattr(self, "fall_started", False):
            if done > 0.05:
                return b""
            self.fall_started = True
        phase = getattr(self, "fall_phase", FALL_CAN)
        out = b""
        # The client has its own height check (helpers/move_unit.MoveUnit.checkBattleGroundHeight): at
        # heightCanOpenParachute it sends changeFallPhase(CAN_OPEN), at heightMustOpenParachute it fires
        # TRIGGER_OPEN_PARACHUTE itself (07.10). chute_client (trigger "chute client") leaves both to it.
        client_chute = getattr(self, "chute_client", os.environ.get("CHUTE_MODE", "server") == "client")
        if phase < FALL_BEFORE_OPEN and done >= 0.02:
            phase = FALL_BEFORE_OPEN
            out += prop_update("BattleGroundAvatar", AVATAR_ID, "battleState", i8(STATE_PARACHUTE))
        elif client_chute:
            pass
        elif phase == FALL_BEFORE_OPEN and done >= float(os.environ.get("CHUTE_BUTTON", "0.6")):
            phase = FALL_CAN_OPEN
        # fallPhase 5 sent by the server only changes the HUD icon (measured 2026-11-26: speed stayed 162
        # km/h); the canopy needs the client's own button (TRIGGER_OPEN_PARACHUTE). Late fallback only.
        elif phase == FALL_CAN_OPEN and done >= float(os.environ.get("CHUTE_AUTO", "0.95")):
            phase = FALL_OPENED
            self.chute_open = True
        if phase == getattr(self, "fall_phase", FALL_CAN):
            return b""
        self.fall_phase = phase
        log("      [BATTLE] fall %.0f%% (y %.0f) -> fallPhase %d" % (done * 100, y, phase))
        return out + prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(phase))

    def handle(self, msgid, payload, log=print):
        """Reply bytes (possibly empty) for one client message."""
        _adopt(self)
        req = decode_request(msgid, payload)
        if req is None:
            return b""
        eid, entity, name, args = req
        self.seen.add((entity, name))
        if name not in NOISY:
            log("      [BATTLE] <- %s(%s).%s args=%s" % (entity, eid, name, args.hex()))
        if (wr := __import__("battle_world").hook_handle(self, eid, entity, name, args, log)) is not None: return wr   # lane 5
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
            if getattr(self, "chute_open", False):     # fall() again just before touchdown: keep the canopy
                return b""
            phase = int(os.environ.get("FALL_REPLY_PHASE", "3"))
            self.fall_phase = phase
            log("      [BATTLE] fall -> fallPhase %d" % phase)
            return prop_update("BattleGroundAvatar", AVATAR_ID, "fallPhase", i8(phase))
        if entity == "BattleGroundAvatar" and name in ("changeFallPhase", "changeGlidePhase") and args:
            phase = struct.unpack("<b", args[:1])[0]
            prop = "fallPhase" if name == "changeFallPhase" else "glidePhase"
            if prop == "fallPhase":
                self.fall_phase = phase
                if phase == FALL_OPENED:                 # the player opened the parachute (client button)
                    self.chute_open = True
            log("      [BATTLE] %s(%d) -> %s %d" % (name, phase, prop, phase))
            return prop_update("BattleGroundAvatar", AVATAR_ID, prop, i8(phase))
        # Jump button (UIBattlegroundsFall.doOnBtnJumpPlaneClick -> cell.requestGetOffPlane(), exposed
        # index 77; logged as stopHeal before the decoder's shift fix). Release as in FLIGHT_STEPS: off the
        # plane, lifted to the flight point, CAN_FALL; the client then free-falls on its own physics,
        # sends fall() (answered above with fallPhase 3) and on_position lands it.
        if entity == "BattleGroundAvatar" and name == "requestGetOffPlane":
            import time
            if getattr(self, "jump_y", None) is not None:      # already released (end of route / double tap)
                return b""
            if getattr(self, "flight", None):
                start = self.plane_position(time.time())[0]    # where the plane is now
            else:
                start = getattr(self, "jump_point", None) or FLIGHT_START
            return self.release_from_plane(start, log)
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
            self.collected = getattr(self, "collected", 0) + 1
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
    # bit path = index (enough bits for the list) + one "more" bit, padded to whole bytes: 2 bytes for
    # BattleGroundAvatar (495 -> 9 + 1 bits), 1 byte for BattleGroundSpace (95 -> 7 + 1). A fixed 2-byte
    # path shifted every zone value by one byte (radius x 256 on the client, 2026-11-26).
    total = (len(lst) - 1).bit_length() + 1
    nbytes = (total + 7) // 8
    path = ((idx << 1) << (8 * nbytes - total)).to_bytes(nbytes, "big")
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

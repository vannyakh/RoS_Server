"""Shared match rooms (lane 6, docs/MULTIPLAYER_DESIGN.md).

Each client keeps its own battle_flow.Match (own-player state) and its own avatar id (AVATAR_ID,
10003). A Room groups the clients of one match: every other member appears to a client as a
non-player BattleGroundAvatar with id PUBLIC_BASE + slot (per-viewer aliasing, design section 4).

Hooks (ros_server.GateUDP, one line each): join() in _enter_battle, on_client_msgs() in the in-battle
message loop, on_reply() in _send_bundle, leave() when the player returns to the lobby.

ROOM_MODE=shared (default) | solo. ROOM_GHOST=on adds, for each client, a server-side member that
mirrors that client's own position ROOM_GHOST_OFFSET to the side (one-client test of the spawn and
relay bytes; design section 9; or create logs/room_ghost.on). Server output only: no client code is touched.
"""
import math
import os
import pickle
import struct
import time

import battle_flow
import bwdefs

PUBLIC_BASE = int(os.environ.get("ROOM_PUBLIC_BASE", "11000"))
ROOM_MAX = int(os.environ.get("ROOM_MAX", "100"))
JOIN_WINDOW = float(os.environ.get("ROOM_JOIN_WINDOW", "120"))     # s after a room opens
RELAY_HZ = float(os.environ.get("ROOM_RELAY_HZ", "10"))
STALE_SECS = float(os.environ.get("ROOM_STALE_SECS", "60"))        # no message for this long = gone
CAMP_SOLO = 30                                                     # const.CampType.AvatarSolo

MSG_POS_IMPLICIT, MSG_POS_EXPLICIT = 2, 3       # client -> server: pos 3f + dir 3f (msg 3: spaceID, vehicleID first)

# Rooms survive importlib.reload of this module.
try:
    ROOMS
except NameError:
    ROOMS = []
    BY_ADDR = {}
    _NEXT_ROOM = [1]


def _log(msg):
    print("      [ROOM] " + msg)


class Member:
    def __init__(self, slot, addr, name, gid, char, outfit, mirror_of=None):
        self.slot, self.addr, self.name, self.gid, self.char = slot, addr, name, gid, char
        self.outfit = outfit
        self.public_id = PUBLIC_BASE + slot
        self.mirror_of = mirror_of        # ghost: addr of the client it mirrors
        self.team_id = slot + 1
        self.pos = None
        self.dir = (0.0, 0.0, 0.0)
        self.t_seen = self.t_join = time.time()
        self.alive = True


class Room:
    def __init__(self, mode="shared"):
        self.id = _NEXT_ROOM[0]
        _NEXT_ROOM[0] += 1
        self.mode = mode
        self.t_open = time.time()
        self.members = []                 # Member, join order
        self.seen = {}                    # viewer addr -> {public_id}
        self.last_relay = {}              # (viewer addr, public_id) -> (t, pos, dir)
        self.map_id = int(os.environ.get("BATTLE_MAP", "700"))

    def open(self):
        return (self.mode == "shared" and time.time() - self.t_open < JOIN_WINDOW
                and len(self.members) < ROOM_MAX)

    def real(self):
        return [m for m in self.members if m.addr is not None]

    def member(self, addr):
        return next((m for m in self.members if m.addr == addr), None)

    def free_slot(self):
        used = {m.slot for m in self.members}
        return next(i for i in range(ROOM_MAX * 2) if i not in used)

    def views(self, subject):
        """(viewer addr, entity id on that viewer) for everyone who should see `subject`."""
        if subject.mirror_of is not None:
            return [(subject.mirror_of, subject.public_id)]
        return [(m.addr, subject.public_id) for m in self.real() if m is not subject]

    def subject_pos(self, subject):
        """Position of a member; a ghost is its client's position moved ROOM_GHOST_OFFSET along x."""
        if subject.mirror_of is None:
            return subject.pos
        src = self.member(subject.mirror_of)
        if src is None or src.pos is None:
            return None
        off = float(os.environ.get("ROOM_GHOST_OFFSET", "5"))
        return (src.pos[0] + off, src.pos[1], src.pos[2])

    def subject_dir(self, subject):
        if subject.mirror_of is None:
            return subject.dir
        src = self.member(subject.mirror_of)
        return src.dir if src is not None else (0.0, 0.0, 0.0)


# ---- entity bytes -----------------------------------------------------------------------------------
def _i32(v): return struct.pack("<i", int(v))
def _arr(ids): return struct.pack("<I", len(ids)) + b"".join(_i32(i) for i in ids)


_NONE = bwdefs.blob(pickle.dumps(None, protocol=2))


def avatar_values(room, m):
    """createEntity values of another player's BattleGroundAvatar (design section 5)."""
    import hero_rules
    char = hero_rules.normalize_hero(m.char)
    name = m.name.encode("utf-8")
    v = {
        "mapID": _i32(room.map_id),
        "characterType": struct.pack("<I", char),
        "gender": _i32(hero_rules.hero_gender(char)),
        "nickname": bwdefs.blob(name),
        "cellGID": struct.pack("<Q", int(m.gid or 0)),
        "campType": struct.pack("<BQQB", CAMP_SOLO, 0, m.team_id, 0),
        "battleGroundTeamID": _i32(m.team_id),
        "hp": _i32(battle_flow.MAX_HP), "maxHp": _i32(battle_flow.MAX_HP), "actualHP": _i32(battle_flow.MAX_HP),
        "dtsWeapon3": _i32(1301), "dtsWeapon5": _i32(1301), "dtsCurWeapon": _i32(5),
        "isVisible": struct.pack("<b", int(os.environ.get("ROOM_VISIBLE", "1"))),
    }
    for p in ("curJetBag", "curJetBagCooler", "curJetBagStabilizer", "curRocketShose", "jumpRobotCombinationInfo"):
        v[p] = _NONE
    o = m.outfit
    if o is not None:
        for kind, prop in (("body", "dtsBodyAppearanceList"), ("wear", "dtsWearableAppearanceList"),
                           ("weapon", "dtsWeaponAppearanceList"), ("vehicle", "dtsVehicleAppearanceList"),
                           ("bgprop", "dtsBattlegroundPropAppearanceList")):
            ids = [int(i) for i in getattr(o, kind, []) or []]
            if ids:
                v[prop] = _arr(ids)
        if int(getattr(o, "aircraft", 0) or 0):
            v["dtsShowAircraftAppearanceID"] = _i32(o.aircraft)
        if int(getattr(o, "jetwings", 0) or 0):
            v["lastJetWingsID"] = _i32(o.jetwings)
        try:
            import json
            slots = json.load(open(os.path.join(battle_flow.HERE, "extract", "appearance_slots.json"),
                                   encoding="utf-8"))["items"]
            for i in getattr(o, "wear", []) or []:
                rule = slots.get(str(int(i)))
                if rule and rule[0] == "wear" and str(rule[1]).startswith("cloth"):
                    v[rule[1]] = _i32(i)
        except Exception as e:
            _log("appearance slots unavailable: %r" % (e,))
    return v


def avatar_create(eid, room, m, pos, direction):
    """enterAoI + createEntity(BattleGroundAvatar).
    ROOM_CE=empty (default): no property stream (the client builds its default dictionary), then the
      values as property updates (update-list index, verified on the own BattleGroundAvatar).
      2026-11-26: ROOM_CE=full (all 219 props, mask flag 0) desynced at the first PYTHON values
      ("Failed to unpickle", "PythonDataType: Not enough data") and the client crashed (SIGSEGV), so the
      client's createEntity list for BattleGroundAvatar is NOT battle_flow.other_client_props.
    ROOM_CE=mask: bitmask + set values (same list, so same risk)."""
    values = avatar_values(room, m)
    ce = os.environ.get("ROOM_CE", "empty")
    if ce == "empty":
        data = b"\x00\x00"                             # flag, compression type; nothing after
        upd = b""
        for name in os.environ.get("ROOM_CE_PROPS", "mapID,characterType,gender,nickname,cellGID,campType,"
                                   "battleGroundTeamID,maxHp,hp,actualHP,isVisible").split(","):
            if name in values:
                upd += battle_flow.prop_update("BattleGroundAvatar", eid, name, values[name])
    elif ce == "mask":
        data = battle_flow.prop_data("BattleGroundAvatar", values)
    else:
        D = battle_flow.defs()
        data = b"\x00\x00\x00" + b"".join(
            values[n] if n in values else bwdefs.encode_default(D.resolve(t), D.defaults.get(n))
            for n, t, _ in battle_flow.other_client_props("BattleGroundAvatar"))
    yaw = direction[2] if direction else 0.0          # Direction3D (roll, pitch, yaw)
    payload = (struct.pack("<IH", eid, battle_flow.client_type("BattleGroundAvatar")) + struct.pack("<3f", *pos)
               + battle_flow._direction(yaw, 0.0, 0.0) + data)
    out = battle_flow.enter_aoi(eid) + battle_flow._var16(battle_flow.MSG_CREATE_ENTITY, payload)
    return out + (upd if ce == "empty" else b"")


# ---- gateway hooks ------------------------------------------------------------------------------------
def _send(gate, addr, data):
    bf = gate._last_bf.get(addr)
    if bf is None or not data:
        return
    gate._send_bundle(addr, data, gate._last_client_seq.get(addr), bytes(bf))


def _reload_if_changed():
    """Pick up edits of this file at the next START (rooms survive; ros_server imports per call)."""
    import importlib, sys
    mod = sys.modules[__name__]
    mt = os.path.getmtime(__file__)
    if mt != globals().setdefault("_MTIME", mt):
        globals()["_MTIME"] = mt
        importlib.reload(mod)
        return True
    return False


def join(gate, addr, name, gid, char, outfit):
    """START: put `addr` in the newest open room (or a new one)."""
    if _reload_if_changed():
        return globals()["join"](gate, addr, name, gid, char, outfit)   # the reloaded function
    leave(gate, addr)
    mode = os.environ.get("ROOM_MODE", "shared")
    room = next((r for r in reversed(ROOMS) if r.open()), None) if mode == "shared" else None
    if room is None:
        room = Room(mode)
        ROOMS.append(room)
        _log("room %d opened (%s)" % (room.id, mode))
    m = Member(room.free_slot(), addr, name or "Player", gid, char, outfit)
    room.members.append(m)
    BY_ADDR[addr] = room
    _log("room %d: %s joined as slot %d (public id %d, gid %s); %d client(s)"
         % (room.id, name, m.slot, m.public_id, gid, len(room.real())))
    ghost_flag = os.path.join(os.path.dirname(battle_flow.HERE), "logs", "room_ghost.on")
    if os.environ.get("ROOM_GHOST", "off") == "on" or os.path.exists(ghost_flag):
        g = Member(room.free_slot(), None, "%s_ghost" % (name or "Player"), gid, char, outfit, mirror_of=addr)
        room.members.append(g)
        _log("room %d: ghost of %s as public id %d" % (room.id, name, g.public_id))
    return room


def leave(gate, addr):
    """The player left the match: leaveAoI to everyone who saw it; drop its ghosts."""
    room = BY_ADDR.pop(addr, None)
    if room is None:
        return
    gone = [m for m in room.members if m.addr == addr or m.mirror_of == addr]
    for m in gone:
        room.members.remove(m)
        for viewer, seen in list(room.seen.items()):
            if viewer != addr and m.public_id in seen:
                seen.discard(m.public_id)
                _send(gate, viewer, battle_flow.leave_aoi(m.public_id))
    room.seen.pop(addr, None)
    _log("room %d: %s left; %d client(s)" % (room.id, addr, len(room.real())))
    if not room.real():
        ROOMS.remove(room)
        _log("room %d closed" % room.id)


def _viewer_ready(gate, addr, room):
    """The viewer stands on the loaded map. map_up (first cell call) alone is too early: a
    BattleGroundAvatar created then left the client on its loading screen (2026-11-26). So also:
    the viewer's own position has left the raw spawn point, and ROOM_SPAWN_DELAY s since it joined."""
    match = gate.__dict__.get("_matches", {}).get(addr)
    me = room.member(addr)
    return bool(match is not None and getattr(match, "map_up", 0) and me is not None and _settled(me.pos)
                and time.time() - me.t_join >= float(os.environ.get("ROOM_SPAWN_DELAY", "30")))


def _settled(pos):
    """Not the raw spawn point (0, 0, 0): the client has put the avatar on the terrain."""
    return pos is not None and abs(pos[0]) + abs(pos[1]) + abs(pos[2]) > 1.0


def on_client_msgs(gate, addr, msgs):
    """In-battle client messages of `addr`: store its position, relay it, create members not yet seen."""
    room = BY_ADDR.get(addr)
    if room is None:
        return
    me = room.member(addr)
    if me is None:
        return
    now = time.time()
    me.t_seen = now
    for mid, p in msgs:
        if mid == MSG_POS_IMPLICIT and len(p) >= 24:
            me.pos, me.dir = struct.unpack_from("<3f", p, 0), struct.unpack_from("<3f", p, 12)
        elif mid == MSG_POS_EXPLICIT and len(p) >= 32:
            me.pos, me.dir = struct.unpack_from("<3f", p, 8), struct.unpack_from("<3f", p, 20)
    for other in list(room.real()):            # members that stopped talking (crash, no Quit)
        if other is not me and now - other.t_seen > STALE_SECS:
            _log("room %d: %s silent for %.0f s" % (room.id, other.addr, now - other.t_seen))
            leave(gate, other.addr)
    for subject in room.members:
        pos = room.subject_pos(subject)
        src = room.member(subject.mirror_of) if subject.mirror_of is not None else subject
        if pos is None or src is None or not _settled(src.pos):
            continue
        direction = room.subject_dir(subject)
        for viewer, eid in room.views(subject):
            if not _viewer_ready(gate, viewer, room):
                continue
            seen = room.seen.setdefault(viewer, set())
            if eid not in seen:
                seen.add(eid)
                data = avatar_create(eid, room, subject, pos, direction)
                _log("room %d: create %s (id %d) on %s at (%.0f, %.0f, %.0f), %d B"
                     % (room.id, subject.name, eid, viewer, pos[0], pos[1], pos[2], len(data)))
                _send(gate, viewer, data)
                room.last_relay[(viewer, eid)] = (now, pos, direction)
                continue
            t, lpos, ldir = room.last_relay.get((viewer, eid), (0.0, None, None))
            if now - t < 1.0 / RELAY_HZ or (lpos == pos and ldir == direction):
                continue
            room.last_relay[(viewer, eid)] = (now, pos, direction)
            _send(gate, viewer, battle_flow.detailed_position(eid, pos, direction))


# ---- state relay (design section 6) -------------------------------------------------------------------
_FIXED = {0x04: 1, 0x0B: 5, 0x58: 30, 0x59: 36}
_VAR16 = {0x05, 0x06, 0x07, 0x09, 0x0A, 0x0F}
_RELAY_FLAGS = ("ALL_CLIENTS", "OTHER_CLIENTS", "ALL_CLIENT", "OTHER_CLIENT")


def _split(body):
    """Server -> client bundle -> [(msgid, header bytes, payload)]; stops at an unknown id."""
    out, i = [], 0
    while i < len(body):
        mid = body[i]
        if mid in _FIXED:
            n, h = _FIXED[mid], 1
        elif mid in _VAR16 or 0x80 <= mid <= 0xBF or mid >= 0xFD:
            if i + 3 > len(body):
                break
            n, h = struct.unpack_from("<H", body, i + 1)[0], 3
        elif 0xC0 <= mid <= 0xFC:
            if i + 2 > len(body):
                break
            n, h = body[i + 1], 2
        else:
            break
        out.append((mid, body[i:i + h], body[i + h:i + h + n]))
        i += h + n
    return out


def _relay_prop(mid, payload):
    """Name of the own-avatar property a 0xC0|idx / 0xFD message changes, if others should see it."""
    lst = battle_flow.update_prop_list("BattleGroundAvatar")
    if mid == 0xFD:
        total = (len(lst) - 1).bit_length() + 1
        nbytes = (total + 7) // 8
        if len(payload) < 4 + nbytes:
            return None
        idx = (int.from_bytes(payload[4:4 + nbytes], "big") >> (8 * nbytes - total)) >> 1
    else:
        idx = mid & 0x3F
    if idx >= len(lst):
        return None
    name, _t, flags = lst[idx]
    return name if flags in _RELAY_FLAGS else None


def on_reply(gate, addr, body):
    """Bytes the gateway is about to send to `addr`: property updates of its own avatar that other
    clients see (pose, hp, battleState, weapons, planeID ...) are re-sent to the other members with the id
    swapped to this player's public id."""
    room = BY_ADDR.get(addr)
    if room is None or not body or os.environ.get("ROOM_STATE_RELAY", "on") == "off":
        return
    me = room.member(addr)
    if me is None:
        return
    own = struct.pack("<I", battle_flow.AVATAR_ID)
    subjects = [me] + [g for g in room.members if g.mirror_of == addr]
    relay = []
    for mid, head, payload in _split(body):
        if mid == 0x04:                            # resetEntities: a new space, nothing to relay
            return
        if (mid == 0xFD or 0xC0 <= mid <= 0xFC) and payload[:4] == own:
            name = _relay_prop(mid, payload)
            if name:
                relay.append((name, head, payload[4:]))
    if not relay:
        return
    for subject in subjects:
        for viewer, eid in room.views(subject):
            if eid not in room.seen.get(viewer, ()):
                continue                           # its createEntity carries the state later
            data = b"".join(head + struct.pack("<I", eid) + rest for _n, head, rest in relay)
            _log("room %d: %s -> %s (id %d)" % (room.id, ",".join(n for n, _h, _r in relay), viewer, eid))
            _send(gate, viewer, data)

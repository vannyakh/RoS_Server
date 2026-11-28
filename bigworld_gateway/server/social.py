"""Friends (checklist 29.x, docs/MULTIPLAYER_DESIGN.md section 11).

The client's iFriend calls, answered from one account directory shared by every session
(server/social.json): search, request, accept, refuse, remove, friend list, online status and
suggestions. The other player is told right away when they are online and in the lobby; otherwise
they see it in the list they ask for at their next login.

Read from the client scripts (2026-11-28): FRIEND_TYPE_STRANGER 1, FRIEND 2, REQUEST 5, NEAR 6;
PlayerOnlineStatus OFFLINE 0, MATCHING 2, GAMING 3, IDLE 4, OBSERVING 5;
the status dicts map gid -> (status, inTeam) for every friend: iFriend reads ``status[gid][0]``
(a bare int left everyone offline) and the invite panel unpacks two values by gid (UIMainBattleGroundInvite);
requestFriend(GID, serverID, reason) is acknowledged with onRequestFriendAck(reason, GID).
"""
import os
import struct
import time

import athlete_requests
import local_store

STORE = os.environ.get("SOCIAL_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "social.json")
SERVER_ID = 10001                  # the Athlete's hostID, so no "other server" tag is shown
TYPE_FRIEND, TYPE_REQUEST = 2, 5
OFFLINE, GAMING, IDLE = 0, 3, 4
ONLINE_SECS = 60                   # no packet for this long = offline (PEER_TIMEOUT)
MAX_FRIENDS, MAX_REQUESTS, MAX_RESULTS = 100, 50, 20

REQUESTS = frozenset((
    "getFriendList", "searchPlayerByName", "searchPlayerByGidList", "requestFriend", "acceptFriend",
    "refuseFriend", "removeFriend", "requestFriendOnlineStatus", "requestSuggestFriends",
    "requestRandomOnlinePlayers"))

try:                               # survives importlib.reload
    ONLINE
except NameError:
    ONLINE = {}                    # gid -> client address of its latest friend request


def in_team(gid):
    """Replaced by server/teams.py."""
    return False


def _log(msg):
    print("      [SOCIAL] " + msg)


# ---------- storage ----------

def _profile(gid):
    return local_store.load(STORE).get("p:%d" % gid)


def _links(gid):
    row = local_store.load(STORE).get("r:%d" % gid) or {}
    return {key: [int(g) for g in row.get(key, [])] for key in ("friends", "in", "out")}


def _save_links(gid, links):
    local_store.save(STORE, "r:%d" % gid, links)


def _without(items, gid):
    return [g for g in items if g != gid]


def register(me):
    """Keep the directory entry of a logged-in player up to date (only written when it changed)."""
    row = {key: me.get(key, "") for key in ("nickname", "characterType", "nationalFlag", "portrait")}
    if _profile(me["gid"]) != row:
        local_store.save(STORE, "p:%d" % me["gid"], row)


# ---------- wire ----------

def abstract(gid):
    """One FRIEND_ABSTRACT (alias.xml field order)."""
    row = _profile(gid) or {}
    s = athlete_requests.blob
    i32 = lambda v: struct.pack("<i", v)
    return b"".join((
        i32(SERVER_ID), s(row.get("nickname") or "Player"), struct.pack("<Q", gid),
        struct.pack("<I", int(row.get("characterType") or 0)),
        i32(0), i32(0), i32(0), i32(1), i32(1), i32(0),            # score ... huiliuOnlineTime (levels 1)
        s(row.get("nationalFlag") or ""), s(row.get("portrait") or ""),
        i32(0), s(""), struct.pack("<I", 0), s(""),                # headFrameTag, fbID, intimacy, xmasBall
        i32(0), i32(0), s(""), struct.pack("<b", 0), i32(0)))


def abstracts(gids):
    return struct.pack("<I", len(gids)) + b"".join(abstract(g) for g in gids)


# ---------- online players ----------

def _address(gate, gid):
    addr = ONLINE.get(gid)
    if addr is None or time.time() - gate._last_recv.get(addr, 0) > ONLINE_SECS or not gate._last_bf.get(addr):
        return None
    return addr


def status(gate, gid):
    addr = _address(gate, gid)
    if addr is None:
        return OFFLINE
    return GAMING if gate._in_battle.get(addr) else IDLE


def state(gate, gid):
    """(online status, in a team). The invite panel unpacks exactly two values for every friend."""
    return status(gate, gid), bool(in_team(gid))


def push(gate, gid, body):
    """Send Athlete calls to another player. Not while they are in a match (no Athlete entity there)."""
    addr = _address(gate, gid)
    if addr is None or gate._in_battle.get(addr):
        return False
    gate._send_bundle(addr, body, gate._last_client_seq.get(addr), bytes(gate._last_bf[addr]))
    return True


# ---------- requests ----------

def handle(gate, addr, name, rd, me, call):
    """Reply bytes for one friend request of the player `me`
    ({gid, nickname, characterType, nationalFlag, portrait}). `call(method, args)` builds an Athlete call."""
    gid = int(me["gid"])
    register(me)
    ONLINE[gid] = addr
    links = _links(gid)

    if name == "getFriendList":
        kind = rd.i8() & 0xFF
        listed = links["friends"] if kind == TYPE_FRIEND else links["in"] if kind == TYPE_REQUEST else []
        online = {g: state(gate, g) for g in listed} if kind == TYPE_FRIEND else {}
        return call("onGetFriendList", bytes([kind]) + abstracts(listed) + athlete_requests.py(online))

    if name == "requestFriendOnlineStatus":
        kind = rd.i32()
        online = {g: state(gate, g) for g in links["friends"]}
        return call("onRequestFriendOnlineStatus", struct.pack("<i", kind) + athlete_requests.py(online))

    if name == "searchPlayerByName":
        text = rd.string().strip().lower()
        found = []
        for key, row in local_store.load(STORE).items():
            if key.startswith("p:") and text and text in str(row.get("nickname", "")).lower() and int(key[2:]) != gid:
                found.append((str(row["nickname"]).lower() != text, int(key[2:])))
        _log("search %r -> %d player(s)" % (text, len(found[:MAX_RESULTS])))
        return call("onSearchPlayerByName", abstracts([g for _, g in sorted(found)[:MAX_RESULTS]]))

    if name == "searchPlayerByGidList":
        wanted = [g for g in rd.i32_array() if g != gid and _profile(g)]
        return call("onSearchPlayerByGidList", abstracts(wanted[:MAX_RESULTS]))

    if name == "requestRandomOnlinePlayers":                  # invite panel, "Online Players"
        others = [g for g in ONLINE if g != gid and _address(gate, g)][:MAX_RESULTS]
        return call("onGetRandomOnlinePlayers",
                    abstracts(others) + athlete_requests.py({g: state(gate, g) for g in others}))

    if name == "requestSuggestFriends":
        others = [g for g in ONLINE if g != gid and g not in links["friends"] and _address(gate, g)]
        return call("onRequestSuggestFriends", abstracts(others[:MAX_RESULTS]))

    other = rd.u64()
    if name == "requestFriend":
        rd.i32()                                    # serverID (one server)
        reason = rd.i8() & 0xFF
        ack = call("onRequestFriendAck", bytes([reason]) + struct.pack("<Q", other))
        theirs = _links(other)
        if other == gid or not _profile(other) or other in links["friends"]:
            return ack if other != gid else b""
        if other in links["in"]:                    # they already asked: this accepts
            return ack + _accept(gate, gid, other, call)
        if gid not in theirs["in"] and len(theirs["in"]) < MAX_REQUESTS:
            theirs["in"].append(gid)
            links["out"] = _without(links["out"], other) + [other]
            _save_links(other, theirs)
            _save_links(gid, links)
            sent = push(gate, other, call("onGetRequest", abstract(gid)))
            _log("request %d -> %d (%s)" % (gid, other, "delivered" if sent else "stored"))
        return ack

    if name == "acceptFriend":
        return _accept(gate, gid, other, call) if other in links["in"] else b""

    if name == "refuseFriend":
        links["in"] = _without(links["in"], other)
        _save_links(gid, links)
        theirs = _links(other)
        theirs["out"] = _without(theirs["out"], gid)
        _save_links(other, theirs)
        return call("onRemoveRequest", struct.pack("<Q", other))

    if name == "removeFriend":
        for mine, yours in ((gid, other), (other, gid)):
            row = _links(mine)
            row["friends"] = _without(row["friends"], yours)
            _save_links(mine, row)
        push(gate, other, call("onRemoveFriend", struct.pack("<Q", gid)))
        _log("removed %d <-> %d" % (gid, other))
        return call("onRemoveFriend", struct.pack("<Q", other))
    return b""


def _accept(gate, gid, other, call):
    mine, theirs = _links(gid), _links(other)
    if len(mine["friends"]) >= MAX_FRIENDS or len(theirs["friends"]) >= MAX_FRIENDS:
        return b""
    for row, friend in ((mine, other), (theirs, gid)):
        row["in"] = _without(row["in"], friend)
        row["out"] = _without(row["out"], friend)
        if friend not in row["friends"]:
            row["friends"].append(friend)
    _save_links(gid, mine)
    _save_links(other, theirs)
    push(gate, other, call("onUpdateFriend", abstract(gid) + b"\x01"))
    _log("friends %d <-> %d" % (gid, other))
    return call("onRemoveRequest", struct.pack("<Q", other)) + call("onUpdateFriend", abstract(other) + b"\x01")

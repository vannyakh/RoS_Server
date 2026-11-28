"""Hall teams (checklist 17.x): invite a friend, accept, leave, kick, ready, and the leader's START.

Dances: playHallTeamAnimation(INT32 prop) -> the others get syncHallTeamAnimation(GID, STRING anim,
INT8 loop); names from the client's hall prop table (extract/hall_team_anims.json).

iHallTeam, read from the client defs and scripts (2026-11-28):
  inviteHallTeamPlayer(GID, STRING nickname, INT32 teamType, INT32) -> the target gets
  onInvitedToHallTeam(INT64 teamID, STRING inviter, INT32 teamType, GID inviter, INT32 secs, STRING);
  acceptHallTeamInvitation(INT64 teamID) -> onEnterHallTeam(INT32 teamType, GID leader, INT8 size,
  ARRAY<HALL_TEAM_MEMBER_CLIENT>, INT32 mapGroup, BOOL, BOOL); the others get addHallTeamMember.

The team lobby shows the leader's theme: members get onUpdateDtsHallThemeID(leader's theme), and their
own again when they leave (display only, nothing is saved).

Teams live in memory. The lobby is shared; inside a match the team members are still separate solo
players (no team display, no revive). The solo START path (battle/session.HallMatchSession) is
unchanged: `handle` returns None whenever it does not own the request.
"""
import json
import os
import struct

import athlete_requests
import social

TEAM_SIZE = 4
INVITE_SECS = 30

REQUESTS = frozenset((
    "createHallTeam", "inviteHallTeamPlayer", "acceptHallTeamInvitation", "refuseHallTeamInvitation",
    "ignoreHallTeamInvitation", "leaveHallTeam", "kickHallTeamMember", "getReadyForBattleGround",
    "notReadyForBattleGround", "matchBattleGround", "assignHallTeamLeader", "playHallTeamAnimation"))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract", "hall_team_anims.json"),
          encoding="utf-8") as _fh:
    ANIMS = {int(k): v for k, v in json.load(_fh).items()}      # prop id -> [animation, loop]

try:                      # survives importlib.reload
    TEAMS
except NameError:
    TEAMS = {}            # team id -> {"id", "mode", "leader", "members": {gid: address}}
    INVITES = {}          # invited gid -> {team ids}
    _NEXT = [1]


def _log(msg):
    print("      [TEAM] " + msg)


def team_of(gid):
    return next((t for t in TEAMS.values() if gid in t["members"]), None)


social.in_team = lambda gid: len((team_of(gid) or {}).get("members", ())) > 1


def _new_team(gid, addr, mode):
    team = {"id": _NEXT[0], "mode": mode, "leader": gid, "members": {gid: addr}}
    _NEXT[0] += 1
    TEAMS[team["id"]] = team
    return team


def _others(team, gid):
    return [g for g in team["members"] if g != gid]


def _member_blob(gate, requester, addr):
    """HALL_TEAM_MEMBER_CLIENT of the player at `addr` (their account state has to be loaded)."""
    gate._enter_addr(addr)
    try:
        return gate._hall_team_member(addr, in_world=False)
    finally:
        gate._enter_addr(requester)


def _theme(gate, requester, owner, call):
    """The calls that show the lobby (theme and display vehicles) of the player at address `owner`."""
    gate._enter_addr(owner)
    try:
        theme, vehicles = gate._hall_theme(owner)
    finally:
        gate._enter_addr(requester)
    return (call("onUpdateDtsHallThemeID", struct.pack("<i", theme))
            + call("onUpdateHallVehicleAppearanceList",
                   struct.pack("<I", len(vehicles)) + b"".join(struct.pack("<i", v) for v in vehicles)))


def _new_leader(gate, requester, team, leader, call):
    """Make `leader` the team leader and tell everyone else; returns the same calls for `requester`."""
    team["leader"] = leader
    body = (call("updateHallTeamLeaderGID", struct.pack("<Q", leader))
            + _theme(gate, requester, team["members"][leader], call))
    for member, address in team["members"].items():
        if address != requester:
            social.push(gate, member, body)
    return body


def _enter_team(gate, addr, team, call):
    members = [_member_blob(gate, addr, a) for a in team["members"].values()]
    size = TEAM_SIZE if len(members) > 1 else 1
    return call("onEnterHallTeam",
                struct.pack("<iQb", team["mode"], team["leader"], size) + struct.pack("<I", len(members))
                + b"".join(members) + struct.pack("<i", 1) + b"\x00\x00")


def leave(gate, requester, gid, call):
    """Take `gid` out of their team and tell the others. True if they were in one."""
    team = team_of(gid)
    if team is None:
        return False
    del team["members"][gid]
    if not team["members"]:
        del TEAMS[team["id"]]
        return True
    for other in team["members"]:
        social.push(gate, other, call("delHallTeamMember", struct.pack("<Q", gid)))
    if team["leader"] == gid:
        body = _new_leader(gate, requester, team, next(iter(team["members"])), call)
        for member, address in team["members"].items():
            if address == requester:                # the requester stays in this team (prune)
                social.push(gate, member, body)
    _log("%d left team %d (%d left)" % (gid, team["id"], len(team["members"])))
    return True


def _prune(gate, gid, addr, call):
    """Drop teammates whose connection is gone, and any team `gid` belonged to on an older login."""
    team = team_of(gid)
    if team is None:
        return
    if team["members"][gid] != addr:            # logged in again: the client has no team any more
        leave(gate, addr, gid, call)
        return
    for other in _others(team, gid):
        if social.status(gate, other) == social.OFFLINE or social.ONLINE.get(other) != team["members"][other]:
            leave(gate, addr, other, call)


def _ready(gate, team, gid, ready, call):
    body = call("syncReadyState", struct.pack("<QBB", gid, ready, 0))
    for other in _others(team, gid):
        social.push(gate, other, body)
    return body


def _start_match(gate, team, leader, call, schedule):
    """The leader pressed START: the other members go into the same match."""
    now = int(athlete_requests.game_now())
    matching = call("syncMatchState", struct.pack("<hqB", 2, now, 0) + athlete_requests.py(None))
    for other in _others(team, leader):
        addr = team["members"][other]
        if social.push(gate, other, matching):
            gate._handoff_bf[addr] = bytes(gate._last_bf[addr])
            schedule(float(os.environ.get("BATTLE_DELAY", "3")), gate._enter_battle, addr)
            _log("team %d start: %d follows the leader" % (team["id"], other))


def handle(gate, addr, name, rd, gid, nickname, call, schedule):
    """Reply bytes, or None to leave the request to the solo hall code."""
    social.ONLINE[gid] = addr
    _prune(gate, gid, addr, call)
    team = team_of(gid)
    squad = team is not None and len(team["members"]) > 1

    if name == "createHallTeam":
        mode = rd.i32()
        rd.i = 0                                    # the solo handler reads it again
        if squad:                                   # keep the squad; the leader sets the mode
            if team["leader"] == gid:
                team["mode"] = mode
                return _enter_team(gate, addr, team, call)
            return _enter_team(gate, addr, team, call) + _theme(gate, addr, team["members"][team["leader"]], call)
        if team is None:
            _new_team(gid, addr, mode)
        else:
            team["mode"] = mode
        return None

    if name == "inviteHallTeamPlayer":
        target = rd.u64()
        rd.string()                                 # the target's nickname
        mode = rd.i32()
        reply = b""
        if team is None:
            team = _new_team(gid, addr, mode)
            reply = _enter_team(gate, addr, team, call)
        if target == gid or target in team["members"] or len(team["members"]) >= TEAM_SIZE:
            return reply
        invite = call("onInvitedToHallTeam",
                      struct.pack("<q", team["id"]) + athlete_requests.blob(nickname)
                      + struct.pack("<iQi", team["mode"], gid, INVITE_SECS) + athlete_requests.blob(""))
        sent = social.push(gate, target, invite)
        if sent:
            INVITES.setdefault(target, set()).add(team["id"])
        _log("%d invites %d to team %d (%s)" % (gid, target, team["id"], "sent" if sent else "not reachable"))
        return reply

    if name == "acceptHallTeamInvitation":
        wanted = struct.unpack_from("<q", rd.b, 0)[0]
        target = TEAMS.get(wanted)
        invited = wanted in INVITES.get(gid, ())
        INVITES.pop(gid, None)
        if not invited or target is None or gid in target["members"] or len(target["members"]) >= TEAM_SIZE:
            return b""
        reply = b""
        if leave(gate, addr, gid, call) and squad:
            reply = call("onLeaveHallTeam", b"")
        target["members"][gid] = addr
        mine = call("addHallTeamMember", _member_blob(gate, addr, addr))
        for other in _others(target, gid):
            social.push(gate, other, mine)
        _log("%d joined team %d (%d members)" % (gid, wanted, len(target["members"])))
        return (reply + _enter_team(gate, addr, target, call)
                + _theme(gate, addr, target["members"][target["leader"]], call))

    if name in ("refuseHallTeamInvitation", "ignoreHallTeamInvitation"):
        INVITES.pop(gid, None)
        return b""

    if name == "leaveHallTeam":
        leave(gate, addr, gid, call)
        return call("onLeaveHallTeam", b"") + _theme(gate, addr, addr, call)

    if name == "kickHallTeamMember":
        target = rd.u64()
        if team and team["leader"] == gid and target in team["members"] and target != gid:
            social.push(gate, target,
                        call("onLeaveHallTeam", b"") + _theme(gate, addr, team["members"][target], call))
            leave(gate, addr, target, call)
            return call("delHallTeamMember", struct.pack("<Q", target))
        return b""

    if name == "playHallTeamAnimation":
        prop = rd.i32()
        if team and prop in ANIMS:
            anim, loop = ANIMS[prop]
            body = call("syncHallTeamAnimation",
                        struct.pack("<Q", gid) + athlete_requests.blob(anim) + struct.pack("<b", loop))
            for other in _others(team, gid):
                social.push(gate, other, body)
        return b""                                  # the dancer's own client already plays it

    if name == "assignHallTeamLeader":
        target = rd.u64()
        if not team or team["leader"] != gid or target == gid or target not in team["members"]:
            return b""
        _log("%d is now the leader of team %d" % (target, team["id"]))
        return _new_leader(gate, addr, team, target, call)

    # ready / start: only squads are handled here
    if not squad:
        return None
    if name == "getReadyForBattleGround":
        if team["leader"] == gid:
            return None                             # the leader runs the normal START sequence
        return _ready(gate, team, gid, 1, call)
    if name == "notReadyForBattleGround":
        if team["leader"] == gid:
            return None
        return _ready(gate, team, gid, 0, call)
    if name == "matchBattleGround":
        if team["leader"] != gid:
            return b""
        _start_match(gate, team, gid, call, schedule)
        return None                                 # then the leader enters as usual
    return b""

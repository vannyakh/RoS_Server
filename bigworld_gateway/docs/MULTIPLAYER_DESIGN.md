# Multiplayer design: one match per room (lane 6)

Status: design, 2026-11-26. Owner: lane 6 (`server/match_room.py`). Sections 17, 18, 29 of
[RESTORATION_CHECKLIST.md](RESTORATION_CHECKLIST.md).

## 1. Today

`GateUDP` (`server/ros_server.py`) keys everything by the client's UDP address:
`_sess[addr]` (account session, `_activate(sess)` loads that player's account state), `_last_bf[addr]`
(Blowfish key), `_in_battle[addr]`, `_matches[addr]` (`battle_flow.Match`, created by `_battle_match`),
`_battle_t0[addr]` (countdown clock). Every client therefore gets its own private `Match`, and every
client's own avatar has the same entity id, `AVATAR_ID` = 10003 (env, used ~40 times in `battle_flow.py`).
No message from one client ever reaches another.

## 2. Evidence the design rests on

All of these are already verified on the live client, for other entity types:

| Message | Format | Verified with |
|---|---|---|
| `createEntity` (id 9, var16) | `id u32, type u16, pos 3f, dir 3×int8, flag u8, compression u8, mask flag u8, bitmask ceil(N/8), values` — N = ALL_CLIENTS/OTHER_CLIENTS props in parse order (first position, last definition) | BattleGroundSpace, Plane, DtsProp (CREATE_ENTITY_FORMAT.md) |
| `enterAoI` (id 11, fixed 5) | `id u32, alias u8 (0xFF)` before `createEntity` | same |
| `leaveAoI` (id 15, var16) | `id u32` | loot pickup |
| `detailedPosition` (0x58, fixed 30) | `id u32, pos 3f, dir 3f (roll, pitch, yaw), u16 0`; the entity's filter interpolates | the Plane flying its route (LOBBY_FINDINGS, flight) |
| property update (`0xC0\|idx` var8 / `0xFD` var16 + bit path) | idx = position in the update list (flags & 6), same index space for player and non-player entities | own avatar (hp, fallPhase), BattleGroundSpace (zone) |
| client position report | msg 2 (24 B): `pos 3f, dir 3f`; msg 3 (32 B): `spaceID u32, vehicleID u32, pos 3f, dir 3f` (BigWorld `avatarUpdateImplicit` / `Explicit`) | `Match.on_position` / `on_message` read the positions |

From the `.def` files (`bwdefs`): a non-player `BattleGroundAvatar` has **219** createEntity properties
(`battle_flow.other_client_props`). The camp FIXED_DICT `campType (camp u8, legionGID u64, teamID u64,
campWarID u8)` is already sent this way in the own player's cell stream (camp 30 = `CampType.AvatarSolo`;
camp 0 raises `KeyError` in `camp_utils.isEnemy`).

Not yet verified (the first live test answers them, see 9):
- that a non-player `BattleGroundAvatar` builds its model from these properties alone (no Frida
  probe of `BattleGroundAvatar.onEnterWorld` / `prerequisites` for non-players yet; if it fails, the
  client log names the missing attribute, and a read-only `neox_py` probe of that method comes next);
- that its filter takes `detailedPosition` like the Plane's `AvatarFilter` does.

## 3. Room model

```
Room(id, mode, team_size)
  members: {addr: Member}        Member = slot, public_id, gid, nickname, char_type, outfit, team_id,
                                          pos, dir, alive, on_plane, map_up, seen_by: set(addr)
  state:   OPEN -> COUNTDOWN -> FLIGHT -> FIGHT -> END
  clock:   t_open, t_countdown, t_flight, t_zone      (one clock for every member)
  shared:  zone stage centres, door states, loot entities, alive count, kill feed
```

- **Matchmaking.** START (`matchBattleGround`, then `_enter_battle(addr)`) calls
  `match_room.join(gate, addr)`. A client joins the newest room that is still `OPEN`/`COUNTDOWN`
  and has a free slot, else opens a new one. `ROOM_MODE=solo` restores today's behaviour (a room of
  one). `ROOM_JOIN_WINDOW` (default: the countdown) is how long latecomers can still join.
- **One `Match` per player, one `Room` per match.** `battle_flow.Match` stays the per-player state
  (fall phases, hp, inventory, result): that is lane 3's and lane 4's code and already correct for one
  player. The `Room` owns only what must be the same for everybody. `match.room` points at it.
- **Leave / disconnect.** `match_room.leave(gate, addr)` (Quit Game, `requestLeaveDynamicSpace`, channel
  timeout): `leaveAoI(public_id)` to everyone who saw the player, member marked gone, `aliveNum` down.
  The room closes when its last member leaves.

## 4. Entity ids: per-viewer aliasing

Entity ids only need to be unique per client connection. So:

- every client keeps **10003 for its own avatar** (no change to `battle_flow` or `avatar_create_messages`);
- another player appears as **`public_id = 11000 + slot`** (slot = join order in the room, 0..99);
- space 20001, plane 20002 and loot (30000+) keep their ids; each client has its own copy, created by
  its own `Match` as today. Shared loot (one pickup removes it for everyone) moves to the room later
  (lane 4 hook, 18.08).

Any id that refers to a player inside a message (killer, `healEntityID`, `knockDownPlayerID`,
`fallFollowTargetID`, teammate lists) is written per viewer by `room.view_id(viewer, subject)`:
10003 if they are the same client, else the subject's `public_id`.
Robots (lane 3/4 bots) can use 12000+ in the same scheme.

## 5. Other-player spawn (18.01)

**Seen on LDPlayer, 2026-11-26.** A createEntity with all 219 values (mask flag 0) desynced at the first
PYTHON values and crashed the client (SIGSEGV), so the client's createEntity list for a BattleGroundAvatar is
not `other_client_props` (probably the order of the `<Implements>` interfaces). The code now sends createEntity
with an **empty property stream** (the client builds its default dictionary), then the values below as
**property updates** (the update-list index is verified on this entity type): `ROOM_CE=empty`, the default.
That run did not crash. A spawn at the first cell call (`map_up`) left the client on its loading screen, so
the spawn now waits until the viewer's own position has left the raw spawn point and `ROOM_SPAWN_DELAY`
(30 s) has passed since it joined. Reading the real createEntity list from the client (read-only probe of
`EntityDescription` / the client's type table) would allow one message again.

Once the viewer stands on the map and the subject has a position, the room sends the viewer:

```
enterAoI(public_id) + createEntity(public_id, BattleGroundAvatar, subject.pos, subject.dir, values)
```

`values` (masked; everything else is the client's `.def` default):

| property | value | why |
|---|---|---|
| `mapID` | room map (700) | every battle entity carries it |
| `characterType` | subject's hero (20001/20002) | model; the default 0 has no model |
| `gender` | from the hero | dressing (`equip_utils`) |
| `nickname` | subject's name | name plate |
| `cellGID` | subject's gid | team / result rows |
| `campType` | `(30, 0, team_id, 0)` | `camp_utils.isEnemy`; camp 0 raises KeyError |
| `battleGroundTeamID` | team_id | teammate checks (17.08–17.10) |
| `hp`, `maxHp`, `actualHP` | 100 | health bar of others (18.07) |
| `battleState`, `pose` | subject's current | 18.04 |
| `planeID` | 20002 while the subject is on the plane, else 0 | attaches the other player to the viewer's plane |
| `curJetBag`, `curJetBagCooler`, `curJetBagStabilizer`, `curRocketShose`, `jumpRobotCombinationInfo` | pickled `None` | same iAirWar `is not None` checks that broke the own player with `{}` |
| `dtsWeapon3`, `dtsWeapon5` = 1301, `dtsCurWeapon` = 5 | fist | same defaults as the own player |
| `dts*AppearanceList`, `cloth0..8`, `dtsShowAircraftAppearanceID`, `lastJetWingsID` | the subject's outfit | 04.x skins seen by others |

The values are built by the same encoders as the own player's cell stream (`bwdefs`), from the
subject's identity captured at `join` time (`_enter_addr(addr)` first, so the right account is active).

## 6. Movement and rotation relay (18.02, 18.03)

On each position report from client B (msg 2 or 3), the room stores `B.pos, B.dir` and sends every other
member A that has B in view:

```
detailedPosition(B.public_id, B.pos, B.dir)          # 0x58, 30 bytes
```

Throttled to `RELAY_HZ` (default 10) per subject, unchanged positions skipped. The receiving filter
interpolates (as for the plane). If `detailedPosition` turns out not to drive an avatar's filter, the
next candidates are the BigWorld `avatarUpdate*` ClientInterface family (`message_map.txt`), checked
in `libclient.so` before trying.

**State relay (18.04, 18.05, 18.07, 18.11).** Lane 3 and 4 code answers B with property updates of B's
own avatar (`prop_update(..., AVATAR_ID, ...)`). The room scans each reply sent to B: every property update
on id 10003 whose property is `ALL_CLIENTS` or `OTHER_CLIENTS` (`pose`, `battleState`, `hp`,
`dtsCurWeapon`, `dtsWeapon*`, `planeID`, `hasLanded`, `isPutgun`, ...) is re-sent to the other members with
the id swapped to `B.public_id`. `OWN_CLIENT` properties (fallPhase, inventory) are not. Lanes 3 and 4
need no change for this: one hook where battle replies are sent. Client method calls that others must see
(firing effects, emotes) come later, item by item.

## 7. Per-room timeline (lane 3)

What moves from the player's `Match` to the room, with lane 3's agreement:

| | today (per player) | room |
|---|---|---|
| countdown start | `_battle_t0[addr]` + `BATTLE_SPACE_DELAY` | `room.t_countdown`: set when the first member's map is up; a later joiner's space entity carries the same `gameStageStartTime` |
| plane | `match.flight["t0"] = time.time()` in `debug_command("flight")` | `room.t_flight` (one route, one t0): every member's plane is at the same place |
| boarded count | `leftPlayerNumOnPlane 1` | number of members still on the plane |
| zone | `zone_start(now)`, white centre toward the own player | `room.t_zone` and the stage centres chosen once by the room (not toward any one player) |
| `aliveNum`, rank | `RESULT_TOTAL` 100 / last place | live members; rank = alive count when a member dies, 1 for the last one standing |
| `finish` | zone end -> win | last member (or last team) alive -> win |

Per-player state stays in `Match`: fall phases, landing, hp, inventory, the result screen's contents.

## 8. Teams (duo / squad, 17.x)

- **Lobby team (17.01–17.07).** `createHallTeam` stays per player. Invite (`inviteHallTeamPlayer(GID,
  STRING, INT32, INT32)`) is routed by the room module's directory of online sessions (gid -> addr) to the
  invitee as `onInvitedToHallTeam(INT64 teamID, STRING, INT32, GID, INT32, STRING)`;
  `acceptHallTeamInvitation(INT64)` -> `addHallTeamMember(HALL_TEAM_MEMBER_CLIENT)` to every member and
  `onEnterHallTeam` to the new one; `leaveHallTeam` -> `onLeaveHallTeam` / `delHallTeamMember`;
  `kickHallTeamMember`, `assignHallTeamLeader` -> `updateHallTeamLeaderGID`. Lane 1 owns the hall team
  handler today: the routing goes in `match_room.py` (a `HallTeams` table) with a one-line hook.
- **Into the match.** The leader's START puts the whole hall team into one room together; each member's
  `team_id` = the hall team id. Solo: `team_id` = slot (everyone is an enemy).
  `campType.teamID` and `battleGroundTeamID` carry it; `teamSize` goes into the room's mode and into
  `onBattleGroundResult` (today fixed 1).

## 9. Test plan

1. **Ghost (one client, now).** `ROOM_GHOST=on`: the room adds a server-side copy of the own player's
   identity as a second member with `public_id` 11001 that mirrors the own position 5 m to the side
   (`detailedPosition` from the real position stream). This exercises exactly the bytes another player
   would get: the createEntity of a `BattleGroundAvatar` and the relay. It is server output only (no client
   Python injected). Evidence for 18.01/18.02 spawn and filter; not a PASS for "two players".
2. **Two clients.** LDPlayer (`emulator-5554`) + the phone (`R3CM90BCXGJ`), or a second LDPlayer
   instance (`ldconsole copy`), both press START within the join window: each sees the other land, walk
   and turn. That is the PASS for 18.01–18.03.

## 10. Hook points

`ros_server.py` (battle part of `GateUDP`, one line each):

| where | call |
|---|---|
| `_enter_battle(addr)`, after the avatar is sent | `match_room.join(self, addr)` |
| in-battle message loop, after `on_position` / `on_message` / `handle` | `match_room.on_client_msgs(self, addr, msgs)` (relay, spawns once `map_up`) |
| where battle replies are sent to `addr` | `match_room.on_reply(self, addr, reply)` (state relay of section 6) |
| Quit Game / lobby transition / channel drop | `match_room.leave(self, addr)` |

`battle_flow.py` (lane 3), needed for section 7, not for 18.01/18.02:

| where | change |
|---|---|
| `debug_command("flight")` | `t0 = match.room.t_flight` if the match has a room |
| `zone_start` / `_zone_next_white` | `t0` and the white centre from `match.room` when present |
| `_zone_damage` / `finish` | `rank` / `total` from `match.room` when present |

## 11. Friends (29.x)

Needs one account directory shared by every session. `match_room.py` keeps the online directory
(gid -> addr, nickname, char) from the gateway sessions; a new `server/social.json` stores per gid:
`friends`, `requests_in`, `requests_out`, `blocked`. Methods (Athlete, `iFriend`):

| client -> server | reply |
|---|---|
| `searchPlayerByName(STRING)` / `searchPlayerByGidList(ARRAY<INT32>)` (29.01) | `FRIEND_ABSTRACT` of matching known accounts (reply method: to find in the client, `UIFriend*`) |
| `requestFriend(GID, INT32, UINT8)` (29.02) | `onRequestFriendAck(UINT8, GID)` to the sender; the target, if online, gets its request list refreshed |
| `acceptFriend(GID)` / `refuseFriend(GID)` (29.03/04) | `onUpdateFriend(FRIEND_ABSTRACT, BOOL)` both sides / request removed |
| `removeFriend(GID)` (29.05) | `onRemoveFriend(GID)` both sides |
| `getFriendList(UINT8 type)` (29.06) | `onGetFriendList(type, ARRAY<FRIEND_ABSTRACT>, PY_DICT)` (today empty) |
| `requestFriendOnlineStatus(INT32)` (29.07) | `onRequestFriendOnlineStatus(INT32, PY_DICT gid -> status)` from the directory |

`FRIEND_ABSTRACT` = serverID, nickname, gid, characterType, score, identifyTagID, isHuiliu, dtsLevel,
dtsRos2Level, huiliuOnlineTime, nationalFlag, portrait, headFrameTag, fbID, intimacyDegree, xmasBallInfo,
hasBackThisSeason, applyFriendRemarkType, applyFriendRemarkContent, ros2PrewarmTag,
ros2WorldLevelPersonaTaskLevel. Which `type` values mean friends / requests / blocked (1, 2, 5 are sent at
login) is read from the client's `iFriend` with a read-only probe before coding.

## 12. Risks and requests

- **Identity is global.** `account_link._login_uid` and `get_account_name()` hold the *last* login.
  `_activate(sess)` switches it per session, so `join` captures identity right after `_enter_addr(addr)`.
  Lane 1: per-session identity would make this safe everywhere.
- **Bandwidth.** 10 Hz × 30 bytes × (N-1) per client is fine for a few clients; AoI distance culling comes
  later (`leaveAoI` beyond ~1000 m).
- **Hot reload.** `match_room` keeps its rooms in a module global that survives `importlib.reload`
  (like `_adopt` in `battle_flow`).

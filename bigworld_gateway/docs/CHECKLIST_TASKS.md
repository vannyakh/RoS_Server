# Checklist lanes: one agent per lane

Splits the 418 open items of [RESTORATION_CHECKLIST.md](RESTORATION_CHECKLIST.md) (518 total, 100 PASS on 2026-11-26)
into lanes. Each lane has its own sections and its own files, so agents in different lanes do not edit the
same code. The procedure every agent follows is in the skill
[`.claude/skills/ros-function-check/SKILL.md`](../.claude/skills/ros-function-check/SKILL.md). Cursor and
Antigravity agents: read that file as your instructions.

## Shared rules

- **LDPlayer is one device.** Only the agent holding the lock drives it or restarts the gateway:
  `.\tools\ldplayer_lock.ps1 acquire -Owner <lane> -Task "<item ids>"`, and `release` when done.
  The lock goes stale after 30 minutes without a `touch`. Lanes 5–7 mostly work without the device and
  should not hold the lock while writing code.
- **Own files only.** If your fix needs a file another lane owns, add a small hook there and put the logic in
  your own module, or leave a note in that lane's "Requests" line below.
- **Order inside a lane:** `CODED` (verify only) → `NOT TESTED` → `PARTIAL` → `FAIL`. Verifying is cheap and
  moves the totals fastest.
- `server/battle_flow.py` is shared by lanes 3, 4 and 5. Lane 3 owns the `Match` timeline (flight, zone,
  `finish`). Lanes 4 and 5 add their own modules and call them from `Match.on_message` with one-line hooks.

## Lanes

| Lane | Owner name | Sections | Open | Device | Owns (write) |
|---|---|---|---|---|---|
| 1 Lobby & account | `lane1-lobby` | 01, 02, 03, 04, 21, 30 | 52 | LDPlayer, phone for 30.11 | `ros_server.py` lobby/login handlers, `loginapp.py`, `profile_screens.py`, `account_link.py` |
| 2 Economy & meta | `lane2-economy` | 22, 23, 24, 25, 26, 27, 28 | 73 | LDPlayer | `athlete_requests.py`, `lobby_mail.py`, `lobby_topup.py`, `lobby_rank.py`, `hero_rules.py`, `server/extract/*.json` |
| 3 Match flow | `lane3-match` | 05, 06, 07, 14, 19, 20 | 57 | LDPlayer | `battle_flow.py` (`Match` timeline, zone, `finish`, `die_call`, `result_call`) |
| 4 Combat & inventory | `lane4-combat` | 08, 09, 10, 11, 12, 13 | 106 | LDPlayer | new `server/battle_items.py` and `server/battle_combat.py`; hooks in `battle_flow.py` |
| 5 World entities | `lane5-world` | 15, 16 | 30 | LDPlayer late | new `server/battle_world.py` (vehicles, airdrops); hooks in `battle_flow.py` |
| 6 Multiplayer & social | `lane6-multi` | 17, 18, 29 | 44 | LDPlayer + phone (two clients) | new `server/match_room.py` (one `Match` per room, other-player `createEntity`, position relay) |
| 7 Admin & backend | `lane7-admin` | 31, 32, 33, 34 | 56 | no | `RoS_Server` and `RoS_Admin` repos (not this one) |

418 open items across the 7 lanes (52 + 73 + 57 + 106 + 30 + 44 + 56).

## Lane notes

**1 Lobby & account.** Quick wins: 02.09 switch account, 02.10 logout, 02.11 banned account (CODED), 04.04/04.05
weapon and vehicle skins in the lobby, 04.10 lobby animations. 30.x settings are CLIENT: one look on screen
each, then PASS.
Requests: lane 6 — per-session identity (login uid, nickname) instead of the global `account_link._login_uid` (MULTIPLAYER_DESIGN.md §12); hall team invite routing hooks for 17.02–17.07. Also lane 7 (31.13-31.15) — the RoS_Server link is off here (no ros_server_v2/.env, and ../../.env is not the sibling RoS_Server/.env), so an admin ban has no effect until it is set; a ban also does not drop a session already logged in (needs a gateway-side check or kick).

**2 Economy & meta.** Many rows are NOT TESTED only: Depot categories (22.04–22.08, 22.10, 22.13–22.15),
skins (23.05–23.13), shop edge cases (24.04, 24.06, 24.11, 24.13, 24.14), Supreme (25.04–25.15).
Known bugs: Supreme monthly page blank (box dates before the device clock), daily sign-in popup returns every
login (`signAwardTime` stream bug, LOBBY_FINDINGS §5). Missions (27.05–27.08, 27.13, 27.14) are not investigated.
Requests: lane 7 (31.16) — per-player mail exists on RoS_Server: GET /api/v1/gateway/accounts/{uid}/mail (lobby_mail.json field names, ids >= 1000000) and POST .../mail/{id}/claim (grants the props once, returns {"props"}); please merge it into `lobby_mail.Mailbox` via two new `account_link` calls. Bug: linked top-up calls account_link.purchase(-total) and the backend answers 422 (price must be >= 0), so Top-Up never credits a linked account (ros_server.py `_topup_reply`); tell lane 7 if you want a backend top-up route for it.

**3 Match flow.** Run first, since lanes 4 and 5 test inside a match. In flight now: 19.06 victory, 19.07 defeat,
14.15 final zone and Exit -> lobby, via `tools/cycles/ld_debug_match.ps1 -TapPlay -TapStart -RequireLobby -ZoneTest`.
Then 05.10 cancel matchmaking, 05.05 (is map 700 Ghillie Island?), 06.x waiting area, 07.10 auto parachute.
Solo-only rows (05.02–05.04, 05.11–05.15, 20.02–20.08) wait for lane 6.
Requests: lane 6 — per-room clock for plane t0, zone t0 + white centre, rank/total from `match.room` (docs/MULTIPLAYER_DESIGN.md §7, §10). Not needed for 18.01/18.02. Also lane 7 (31.03, 31.11, 34.04) — the gateway never POSTs match results; RoS_Server accepts them at POST /api/v1/gateway/accounts/{uid}/matches (GatewayMatchReport).
lane 1 — in `Match.finish` call `exp = profile_screens.grant_match_exp(gid, rank, total, kills)` and put `exp` in
`result_call`'s row `"exp"` (21.07/21.08; the lobby adds it with the level-up popup at its next profile sync).

**4 Combat & inventory.** Start with the single-player inventory loop: map 700 loot spawn table (12.01),
armor/helmet on pickup (12.15, 12.16), healing (11.04–11.08), drop (12.13, 10.32), reload and ammo
(10.15–10.17), fall damage (08.18, 11.09). Hits and damage on players (10.21, 10.24–10.26) need bots or lane 6.
Requests: none yet.

**5 World entities.** No vehicle entities exist yet. Find the vehicle and airdrop entity defs in
`server/extract/entities_out/` and the client handlers first (read-only Frida only, AGENTS.md rule 1).
Requests: none yet.

**6 Multiplayer & social.** The main blocker in the whole checklist: every client gets its own `Match`.
Design the room model before writing code, and agree the hook points in `battle_flow.py` with lane 3.
Unblocks about 60 FAIL rows across sections 05, 06, 10, 11, 17, 18, 19 and 20.
Requests: none yet.

**7 Admin & backend.** RoS_Server is cloned at `Desktop\RoS_Server` (branch `feat/original-client-gateway`; `main`
has no admin or gateway routes) and runs on `127.0.0.1:8000` with its own `.env`. 31–34 CODED rows were checked
over the API on 2026-11-26. Next: ban end-to-end on LDPlayer (needs the link on), disconnect (31.13), config
versioning (32.13, 32.14).
Requests: none yet.

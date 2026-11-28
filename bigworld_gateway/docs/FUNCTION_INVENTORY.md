# Function inventory: Rules of Survival 1.610637.617289 on this gateway

Status of every game function against `ros_server_v2` (gateway `server/ros_server.py`, match logic
`server/battle_flow.py`), as of 2026-11-26. Sources: `docs/LOBBY_FINDINGS.md` sections (§) and the code.

| Mark | Meaning |
|---|---|
| ✅ | Works, verified on LDPlayer |
| 🟢 | Coded, not yet verified in game |
| 🟡 | Partial: the screen works but the data is fixed, empty or single-player only |
| 🔴 | Not implemented |
| ⚪ | Runs on the client; the server only has to not break it |

**The main blocker is multiplayer.** Each connected client gets its own `Match` object, so nobody shares
a world: other players are never created on a client and positions are not relayed. Combat between players,
teams, spectating, a real queue and real placement all depend on this, or on server-side bots.

## 1. Account and lobby

| Function | Status | Notes |
|---|---|---|
| Login | ✅ | `loginapp.py`; per-device uid; RoS_Server link optional (`account_link.py`) |
| Server selection | ✅ | One entry ("Private-Server") from `real/server_list_ad.local.txt` |
| Player profile: name | ✅ | `baseNickname`; renamed from the RoS_Server admin console when linked |
| Player profile: portrait, level, exp bar | ✅ | Default portrait served over FilePicker (`/file/<id>`, `server/portraits/`) + `onAddDtsExp(exp, level)` 12 s after enterHall; level in `saved_accounts.json` `level:<gid>` (§28) |
| My Page, Stats, Credit | ✅ | `profile_screens.py` (§19); zeros without RoS_Server |
| My Page weapon proficiency, match team | 🔴 | `getHighestProficiencyWeapons`, `getAthleteRosMatchTeamBriefData` unanswered (§18) |
| Avatar photo upload | 🔴 | FilePicker / TanTanService not served; the built-in image is used |
| Character customization | ✅ | Gender = character type 20001/20002, wardrobe, wear, hall theme; outfit also shows in matches (§6, §20) |
| Inventory (owned items) | ✅ | Saved locally or in RoS_Server (§7) |
| Shop: store, buy, supply draws | ✅ | Diamonds charged from box/item price (§2, §6) |
| Top-Up | ✅ | Grants diamonds from the PayGoods table, no payment (§20) |
| Mail | ✅ | `lobby_mail.py`, claim saves items (§18) |
| Leaderboard | ✅ | Only the current player is listed (§19) |
| Daily sign-in | 🟡 | Claim works; the popup comes back every login (`signAwardTime` cannot be sent, stream bug §5) |
| Events / Activity panel | 🟡 | Panel opens; the individual event pages are not checked (§19) |
| Supreme Supply monthly page | 🟡 | Blank: monthly boxes are dated before the device clock (§1) |
| Missions, achievements | 🔴 | Not investigated |
| Season / rank progression | 🔴 | No season data; rank score only from RoS_Server profile |
| Friends | 🟡 | `onGetFriendList` answers empty lists (§19) |
| Party creation, invites | 🟡 | Solo hall team only (`onEnterHallTeam`, §3); no invites or other members |
| Settings | ⚪ | Client-only |

## 2. Matchmaking

| Function | Status | Notes |
|---|---|---|
| Mode selection | 🟡 | The client sends the mode; the server always starts the same solo match |
| Map selection | 🔴 | Fixed by `BATTLE_MAP` (700) |
| Queue | 🟡 | Instant: `syncMatchState` MATCHING -> ENTERING, no waiting for players (§3, §4) |
| Room assignment | 🔴 | One private match per client (see the multiplayer blocker) |
| Waiting area (warm-up island) | 🔴 | The player spawns on the ground at (0, 0, 0) during the countdown |
| Ready / countdown | ✅ | "Starting in N s", 79 s from the client's PREPARE_TIME (§14, §15) |
| Match start | ✅ | gameStatus PREPARE -> BEFORE_FIGHT -> FIGHT |

## 3. Aircraft and landing

| Function | Status | Notes |
|---|---|---|
| Flight route | ✅ | Plane flown with `detailedPosition` along `FLIGHT_ROUTE` (§25) |
| Jump | ✅ | `requestGetOffPlane` releases at the plane's position |
| Freefall | ✅ | Server steps `fallPhase` by height (§23) |
| Parachute | ✅ | Opens with the client's button (`changeFallPhase(5)`) |
| Landing | ✅ | Ground HUD after touchdown; camera stays zoomed out after the first landing of a session |
| Team coordination (follow jump) | 🔴 | Needs teams |

## 4. Movement and camera

| Function | Status | Notes |
|---|---|---|
| Walk, sprint | ⚪ | Client physics; positions are read by the server but not relayed |
| Jump | ✅ | `jumpStart` / `jumpEnd` (§14) |
| Crouch, prone (crawl) | ✅ | `changePose` -> `pose` (§14) |
| Swim | ⚪ | Not tested |
| Free look, ADS, camera rotation | ⚪ | Client-only |

## 5. Weapons and combat

| Function | Status | Notes |
|---|---|---|
| Equip | 🟡 | `wpn` test command verified (§12); gun pickup into slot 1/2 coded, not verified on screen |
| Fire | 🟡 | `fire` / `fireEnd` decoded, no server reply or ammo use |
| Reload, fire mode, recoil | 🔴 / ⚪ | No reload or ammo bookkeeping; fire mode and recoil are client-side |
| Hit detection, damage | 🔴 | No targets: no other players or bots |
| Attachments | 🔴 | |
| Grenades | 🔴 | Grenade props spawn; throwing is not answered |
| Elimination, kill feed | 🔴 | |

## 6. Health and inventory

| Function | Status | Notes |
|---|---|---|
| Health | ✅ | Server hp, only zone damage lowers it (§26) |
| Armor, helmet | 🔴 | They go to the bag; `dtsHelmet` / `dtsVest` are not set on pickup, and there is no damage reduction |
| Healing items | 🔴 | |
| Knockdown, revive | 🔴 | Squad feature |
| Pickup | ✅ | `tryPickUp` -> `onAddDtsItem` (§11) |
| Drop | 🔴 | |
| Backpack capacity | 🔴 | No weight or capacity check |
| Loot placement | 🔴 | Only the `loot x y z` test command; nothing in buildings |
| Airdrop / loot crates | 🔴 | |
| Doors | 🟢 | `openElement` / `closeElement` echoed, no client errors; not seen opening on screen (§11) |

## 7. World and vehicles

| Function | Status | Notes |
|---|---|---|
| Map | ✅ | Map 700 loads |
| Minimap | ✅ | Plane path, zone circles |
| Waypoints / markers | ⚪ | Own marker is client-side; not shared with teammates |
| Safe zone | ✅ | 8 stages, shrink, HUD timer (§24) |
| Zone damage | ✅ | Per-stage damage, poison vignette, death at 0 hp (§26) |
| Vehicle spawn, enter/exit, driving, passengers, fuel, collision, damage, boats | 🔴 | No vehicle entities yet |

## 8. Team and results

| Function | Status | Notes |
|---|---|---|
| Team markers, team panel | 🔴 | |
| Voice chat | 🔴 | CC voice service not served |
| Quick chat / text chat | 🔴 | |
| Spectate | 🔴 | `onBattleGroundDie` opens the observe panel; nothing to watch yet |
| Survivor check | 🟡 | Solo: dying = last place, surviving the last circle = win |
| Death / victory screen | 🟢 | `Match.finish` -> `onBattleGroundResult` (index 267); `die_call` sends `onBattleGroundDie({})` first. Not verified |
| Placement | 🟡 | Fixed: rank `RESULT_TOTAL` (100) on death, 1 on win |
| Statistics | 🟡 | Kills 0, distance 0; items collected counted |
| Rewards (GP, exp) | 🔴 | Result rows show 0; nothing is granted |
| Rank update | 🔴 | |
| Return to lobby | ✅ / 🟢 | Quit Game verified (§15); the result screen's Exit sends the same `requestLeaveDynamicSpace` |

### Note on the death screen

On the client (`client/frida/payloads/result_dis.py`), `onBattleGroundDie` calls `_delayShowResult((True, killerInfo))`.
`True` is `isObserve`, so it opens the result UI in spectate mode, meant for squads where teammates are still
alive. `onBattleGroundResult` opens the normal result. A solo death may need only `onBattleGroundResult`;
check this when the screen is tested (Harness §27 sends both).

## Suggested order

1. Verify what is coded: the restart for the profile card, then the death / win screen and Exit -> lobby.
2. Loot placement in buildings for map 700 (server-only, uses the existing pickup path).
3. Armor, helmet, healing and drop (single-player, completes the inventory loop).
4. Rewards: GP and exp from the result screen into the account (exp feeds the new lobby level).
5. Shared match for several clients (one `Match` per room, other-player createEntity, position relay). This unlocks combat, teams, spectate, queue and placement.
6. Vehicles.

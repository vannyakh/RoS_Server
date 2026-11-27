# Player system & character gameplay — restoration tracker

**Authority:** Engineering audit · **Date:** 2026-11-27  
**Client path:** Original APK + LDPlayer + `bigworld_gateway/` (Mercury gateway).  
**Parallel path:** `app/` JSON WebSocket + in-memory `app/game` (custom client / QA simulator — not original-client proof).

**Status vocabulary:** `NOT_CHECKED` | `MISSING` | `BROKEN` | `PARTIAL` | `IMPLEMENTED` | `VERIFIED` | `BLOCKED`

`VERIFIED` requires LDPlayer or authorized device evidence (logs or screenshots). Unit tests alone stay at `IMPLEMENTED`.

Related: [RESTORATION_STATUS.md](RESTORATION_STATUS.md) · [SOLO_GAMEPLAY_STATUS.md](SOLO_GAMEPLAY_STATUS.md) · [GAMEPLAY_FUNCTION_AUDIT.md](GAMEPLAY_FUNCTION_AUDIT.md) · [PLAYER_PROTOCOL_MAPPING.md](PLAYER_PROTOCOL_MAPPING.md) · [PLAYER_STATE_MACHINE.md](PLAYER_STATE_MACHINE.md)

---

## Architecture (where player code lives)

| Concern | Original APK (P0) | JSON simulator (`app/`) |
| --- | --- | --- |
| Persistent profile | `GatewayService`, `/api/v1/gateway`, `app/models/player.py` | `PlayerService`, `GET /api/v1/players/me` |
| Hall / character | `ros_server.py`, `hero_rules.py`, outfit pushes | Register + cosmetics seed |
| In-match runtime | `battle/session.py` **MatchSession**, `battle/player_entity.py`, `battle/modules/*` | `app/game/state.py` `PlayerState`, `simulate.py` |
| Human + bot shared entity | `PlayerRuntimeState` (human `session.player`, bots in `session.combatants`) | Same `PlayerState` for humans and bots in tests |
| Battle inventory | `PropsModule` + legacy `battle_flow.Match` — **separate from hall/depot** | In-memory `PlayerState.inventory` per match |
| Depot / cosmetics | SQL + gateway items; not auto-equipped in match | HTTP `inventory`, `cosmetics_service` |

Do **not** add a second `server/modules/player/` tree. Extend `bigworld_gateway/server/battle/` and `app/game/` in place.

---

## Tracker summary

| Metric | Value |
| --- | --- |
| Checklist rows (owner list) | **109** |
| Mobile-verified | **0** (blocked on RO-113 network path) |
| Gateway unit-tested seams | spawn/fill/zone/props/jump/plane/space/bots |
| Critical LDPlayer blocker | Network Error(15) before hall START — see [testing/solo_first_playable.md](testing/solo_first_playable.md) |

**Recommended repair order (matches owner P0 list):** identity → spawn/lifecycle → movement → health/damage → battle inventory → weapons/combat → sync → vehicles → results.

---

## 1. Account & character — 0/9 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 1.1 | Load persistent player ID | IMPLEMENTED | Gateway gid + SQL `players.id`; JSON JWT subject |
| 1.2 | Create default character | IMPLEMENTED | `GatewayService.set_character`, starter cosmetics |
| 1.3 | Male / female selection | PARTIAL | char 20001/20002; female not re-verified on device |
| 1.4 | Change nickname | PARTIAL | Profile update API; hall re-test open |
| 1.5 | Load avatar | PARTIAL | Portrait fields; FilePicker HTTP incomplete |
| 1.6 | Level & EXP | PARTIAL | Readable; match EXP from gateway battle end not wired |
| 1.7 | Currency sync | PARTIAL | Diamonds/gold paths differ JSON vs gateway |
| 1.8 | Equipped cosmetics | PARTIAL | `equipAppearance`; depot persistence partial |
| 1.9 | Save profile after reconnect | PARTIAL | Mercury keepalives; LDPlayer inactivity drops |

---

## 2. Player spawn — 0/7 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 2.1 | Spawn in preparation area | IMPLEMENTED | Space countdown RO-061; prep timeline |
| 2.2 | Initialize character model | PARTIAL | `createBasePlayer` / BattleGroundAvatar; device unverified |
| 2.3 | Initialize health | IMPLEMENTED | `zone` + `PlayerRuntimeState.max_health`; wire on play |
| 2.4 | Position / rotation sync | PARTIAL | Jump forcedPosition; ClientInterface msg 3 layout unknown |
| 2.5 | Display player name | IMPLEMENTED | Account nickname on avatar create |
| 2.6 | Equipped skins in match | PARTIAL | Appearance lists; historical UI aborts if empty |
| 2.7 | Reset previous battle inventory | IMPLEMENTED | `PlayerRuntimeState.reset_battle_loadout()` on session start |

---

## 3. Movement & controls — 0/13 verified

| # | Function | Status | Notes |
| --- | --- | --- | --- |
| 3.1–3.8 | Joystick, walk, sprint, jump, crouch, prone, swim, vault | PARTIAL / MISSING | Client physics dominant; server echoes `changePose` in legacy `Match.handle`; RO-082/083 backlog |
| 3.9–3.10 | Camera / free look | NOT_CHECKED | Client-local |
| 3.11 | Movement animation | NOT_CHECKED | Client |
| 3.12–3.13 | Collision / anti-cheat validation | MISSING | No server navmesh; verifyClient* logged only |

---

## 4. Aircraft & parachute — 0/8 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 4.1–4.8 | Full chain to ground | IMPLEMENTED (unit) | RO-062 plane, RO-063 jump module; live AC4 open; RO-113 blocked |

---

## 5. Weapon system — 0/12 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 5.1–5.4 | Pickup, equip, switch | PARTIAL | `PropsModule` + `battle_flow`; slots on `session.player.gun_slots` |
| 5.5–5.9 | Aim, fire modes, reload, ammo | MISSING / PARTIAL | No authoritative hit scan on gateway; JSON `simulate._shoot` works |
| 5.10–5.12 | Attachments, drop, anim sync | PARTIAL | Legacy Match; drop RO-079 backlog |

---

## 6. Health & survival — 0/10 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 6.1 | Initialize health | IMPLEMENTED | Zone play phase + `PlayerRuntimeState` |
| 6.2–6.4 | Damage, armor, helmet | PARTIAL | Zone poison; no firearm damage on gateway yet |
| 6.5–6.6 | Healing, cancel heal | MISSING (gateway) | JSON `_tick_heal` IMPLEMENTED |
| 6.7–6.9 | Fall, zone, vehicle damage | PARTIAL | Zone RO-064; fall/vehicle open |
| 6.10 | Eliminate (Solo) | PARTIAL | `set_eliminated()` + results `apply_zone_fatal`; combat death open |

---

## 7. Inventory & loot — 0/11 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 7.1–7.11 | Backpack, pickup, capacity, drops | PARTIAL | `PropsModule` spawn/pickup; stacks on `battle_inventory`; depot separate |

---

## 8. World interaction — 0/8 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 8.1–8.2 | Doors | PARTIAL | `openElement` / `closeElement` in `battle_flow.Match` |
| 8.3–8.6 | Vehicles | MISSING (gateway) | JSON buggy IMPLEMENTED; RO-091 backlog |
| 8.7–8.8 | Minimap / marker | NOT_CHECKED | Client |

---

## 9. Animation & audio — 0/11 verified

| # | Function | Status |
| --- | --- | --- |
| 9.* | All rows | NOT_CHECKED (client-led; server action replies RO-083) |

---

## 10. Results & persistence — 0/11 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 10.1–10.6 | Placement, stats, EXP, currency | PARTIAL | `results.py` RO-071; gateway report API |
| 10.7–10.11 | Lobby return, cleanup | PARTIAL | RO-127 / historical quit; live unverified |

---

## 11. Network & performance — 0/9 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 11.1 | Entity create/remove | IMPLEMENTED (unit) | RO-059 encoders |
| 11.2–11.6 | Position, equipment, health, weapon sync | PARTIAL | Property updates; position decode incomplete |
| 11.7–11.9 | AoI, reconnect, perf | PARTIAL / BLOCKED | RESEND history; RO-113 env |

---

## Immediate blockers (before 120-player scale)

| Blocker | Owner task | Mitigation |
| --- | --- | --- |
| LDPlayer cannot reach hall START | RO-113 | Re-run `bigworld_gateway/client/scripts/setup_emulator.ps1`; align DNS to `config.cmd` `ROS_PC_IP`; clear emulator HTTP proxy `192.168.100.137:8080` |
| No live Solo playable proof | RO-113 | After network fix: Start → 9 bots → plane → parachute → land |
| Gateway combat loop missing | RO-085+ | Shared `PlayerRuntimeState` ready for damage/combat modules |
| Movement server authority | RO-082, RO-083 | Research before implementing replies |
| Position message layout | RO-057, RO-060 | Do not invent 0xBC/0xBD as position |

---

## Code changes this session (2026-11-27)

- Added `bigworld_gateway/server/battle/player_entity.py` — shared human/bot runtime; battle inventory reset.
- Added `bigworld_gateway/server/battle/modules/player_runtime.py` — lifecycle hooks on match timeline.
- Wired `MatchSession.player` / `combatants`; zone HP, props gun slots, jump land position, bot registration.
- Tests: `tests/compatibility/gateway/player/test_player_entity.py`.

**Next engineering tasks (registry):** unblock RO-113 → RO-082 research → RO-083 movement replies → RO-077/084 inventory → RO-085 combat.
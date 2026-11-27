# Private server gameplay roadmap (build 617289)

Priorities derived from [gameplay_function_matrix.json](gameplay_function_matrix.json): implement features that exist in **617289** (`in_build_617289: yes`) where `server_status` is weakest, without violating [AGENTS.md](AGENTS.md) (no NeoX auth bypass, one harness hypothesis per iteration, minimal diffs).

**Harness acceptance:** each milestone should log LDPlayer (`emulator-5554`) and phone (when connected) in [harness/iteration_log.jsonl](../../harness/iteration_log.jsonl) with screenshots under `harness/captures/`.

---

**Phase tracker:** [PHASE_STATUS.md](PHASE_STATUS.md) (A mostly done → **B active** → C in progress → D/E backlog).

## Current snapshot

| Area | Matrix summary | Primary code |
|------|----------------|--------------|
| Login / patch / server list | working | `loginapp.py`, `ros_mock_server.py`, `dns_server.py` |
| Lobby UI + economy | partial | `ros_server.py`, `athlete_requests.py`, `lobby_rank.py`, `lobby_topup.py` |
| START → map load | partial | `createHallTeam`, `matchBattleGround`, `_enter_battle` |
| Drop (plane → land) | partial → strong | `battle_flow.py` `FLIGHT_STEPS`, `Match.flight_tick` |
| Safe zone + zone damage | partial | `Match.zone_tick`, `_zone_damage` |
| Combat / loot / vehicles | stub / none | `Match.handle`, `DtsProp` |
| Match end → lobby | stub | `result_call`, `_transition_to_athlete` |

Detail and blockers: [LOBBY_FINDINGS.md](LOBBY_FINDINGS.md) (sections 1–26).

---

## Phase A — Lobby completeness

**Matrix:** `Account_and_Lobby` (11 functions).

| Target | Functions | Work |
|--------|-----------|------|
| `partial` → `working` | login, server_selection, shop, party_creation | Stabilize regressions; document env flags |
| Close blockers | player_profile, inventory, character_customization | Fix `childBaseClientPropertyList` stream or narrow safe fields; push appearance tables where `dts_appearance_utils` fails |
| Stub → partial | friends, events, missions | Stub friend payloads with test GIDs; flesh Athlete methods for open Activity tabs |
| N/A | settings | Client-only — document, no server work |

**Acceptance:** Enter hall2, hero visible, START opens match timer, Store/Depot/Supply/Top-up usable, no fatal `on_enter` aborts on LDPlayer with **2022-04-20** clock.

---

## Phase B — Matchmaking → battle handoff

**Matrix:** `Matchmaking` (7 functions).

| Target | Work |
|--------|------|
| `match_start` working | Complete ENTERING → `resetEntities` → `BattleGroundAvatar` + cell player for duo/squad sizes (teamSize in `onEnterHallTeam`) |
| `room_assignment` | Synthetic cell space only today; document single-space model |
| `waiting_area` | Optional: prep-zone NPCs are low priority (notice-only feature) |
| Map selection | Env or lobby RPC for map id beyond 700 (Fiord ids from client data — RE first) |

**Acceptance:** Tap START → match timer → load map 700 without manual `BATTLE_ENTER=off` tricks; cancel match returns to lobby.

---

## Phase C — Core BR slice

**Matrix:** `Aircraft_and_Landing`, `World_and_Vehicles` (safe_zone, zone_damage), `Team_and_Results` (subset).

Already largely exercised; close gaps:

| Item | Matrix ids | Work |
|------|------------|------|
| Result screen | elimination, placement, return_to_lobby | On hp 0 or win: `onBattleGroundDie` + `onBattleGroundResult` + verified `_transition_to_athlete` |
| Zone polish | safe_zone, zone_damage | `showCircleNotify` / `updateCircleRestTime` indices; UIDtsMap circles |
| Drop polish | flight_route, parachute, landing | Reduce camera zoom bug; jump from live plane position (partially done §25) |
| Survivor HUD | survivor_check | Decrement `aliveNum`, sync kill feed when bots added |

**Acceptance:** One full solo match: START → drop → land → survive one zone stage → die to zone or debug kill → result UI → lobby.

---

## Phase D — Extended BR

**Matrix:** `Weapons_and_Combat`, `Health_and_Inventory`, `Movement_and_Camera` (server side), `World_and_Vehicles` (vehicles).

Gated on Phase C stability.

| Priority | Functions | Work |
|----------|-----------|------|
| High | pickup, loot_crates, equip_weapon, backpack_capacity | Map 700 spawn table; `dtsBattlegroundPropAppearanceList`; building `openElement` state |
| Medium | fire, damage, reload, healing, armor, helmet | Decode 0xBC/0xBD; server HP model for gunfights |
| Medium | knockdown, revive, team_markers | Requires squad cell logic |
| Low | vehicles (spawn, driving, passengers, vehicle_damage) | `LandCraft` createEntity + position stream |
| Low | grenades, attachments, drop | Prop use RPCs from defs |

**Acceptance:** Pick up ground loot from authored spawns, shoot another entity (bot), heal, die, spectate optional.

---

## Phase E — Meta and HTTP

**Matrix:** remaining lobby/meta; mostly client + CDN.

| Work | Touchpoint |
|------|------------|
| FilePicker / portrait HTTP | `fp.ps.easebar.com`, TanTanService mock |
| Voice / quick chat | Optional mocks; not required for solo BR |
| Season pass / ranked persistence | RoS_Server API + Athlete sync methods |
| Historical LT modes | Notice + script strings only — do not claim without evidence |

**Acceptance:** Documented “out of scope for playable BR” unless user enables meta testing.

---

## Milestone table

| Phase | Category (matrix) | Target `server_status` | Harness signal |
|-------|-------------------|------------------------|----------------|
| A | Account_and_Lobby | majority `working` / `partial` | Lobby screenshot + no SCRIPT traceback |
| B | Matchmaking | `match_start` `working` | START without dev env overrides |
| C | Aircraft + World zone + Results | drop `working`, results `partial`→`working` | Result screen capture |
| D | Weapons + Health + loot | pickup `working`, fire `partial` | Loot + weapon equip screenshot |
| E | Meta | stub documented | N/A |

---

## Maintenance

1. Edit [gameplay_matrix_evidence.yaml](gameplay_matrix_evidence.yaml) when a feature moves forward.
2. Run `python scratch/build_gameplay_matrix.py`.
3. Append [LOBBY_FINDINGS.md](LOBBY_FINDINGS.md) with dated verification notes.
4. Update this roadmap only when phases or acceptance criteria change.

See also [GAMEPLAY_REFERENCE_617289.md](GAMEPLAY_REFERENCE_617289.md) for player-facing behaviour descriptions.
# Rules of Survival — gameplay reference (build 1.610637.617289)

NetEase shut down the live service on **2022-06-27**. This document describes how the original mobile game worked in its late era, with evidence tied to the preserved client **`com.netease.chiji` / `1.610637.617289`** used in this repository—not a redesign or a generic battle-royale summary.

**Related artifacts**

| Artifact | Path |
|----------|------|
| 74-function manifest | [gameplay_function_ids.yaml](gameplay_function_ids.yaml) |
| Per-function evidence + private-server status | [gameplay_function_matrix.json](gameplay_function_matrix.json) |
| Regenerate matrix | `python scratch/build_gameplay_matrix.py` |
| Implementation priorities | [SERVER_GAMEPLAY_ROADMAP.md](SERVER_GAMEPLAY_ROADMAP.md) |
| Wire protocol / lobby RE | [LOBBY_FINDINGS.md](LOBBY_FINDINGS.md) |
| Server architecture | [../../README.md](../../README.md) |

**Three layers of truth** (from preservation practice)

| Layer | Meaning |
|-------|---------|
| Known gameplay | Player-visible behaviour (this doc) |
| Build 617289 | Confirmed or inferred for this APK via extract, notices, Frida read-only probes |
| Private server | What [ros_server.py](../server/ros_server.py) / [battle_flow.py](../server/battle_flow.py) emulate today (`server_status` in the matrix) |

Confidence tags in the matrix: `confirmed_build`, `inferred_from_notice`, `generic_br_lore`.

---

## 1. Complete gameplay lifecycle

```mermaid
flowchart TB
  launch[Launch and patch]
  login[Account login]
  lobby[Main lobby]
  mm[Matchmaking]
  prep[Prep / countdown]
  plane[Aircraft route]
  drop[Jump freefall parachute land]
  br[Loot combat vehicles zone]
  end[Results and lobby return]
  launch --> login --> lobby --> mm --> prep --> plane --> drop --> br --> end --> lobby
```

| Phase | Player experience | BigWorld / NeoX types (617289) |
|-------|-------------------|------------------------------|
| Launch | Patch manifest, language, UniSDK | `patch.*`, `ui.UILogin` |
| Login | Guest or bound account, server list | Mercury LoginApp → BaseApp |
| Lobby | Character, modes, shop, friends | `Athlete` / `PlayerAthlete`, hall scenes |
| Matchmaking | Mode, queue, ready | `iHallTeam`, `createHallTeam`, `matchBattleGround` |
| In match | Map load, HUD, entities | `BattleGroundAvatar`, `PlayerAvatar`, `BattleGroundSpace` |
| Drop | Plane, jump, parachute | `Plane`, `fallPhase`, `requestGetOffPlane` |
| Survival | Zone, loot, combat | `BattleGroundSpace` circles, `DtsProp`, weapons |
| End | Rank, rewards | `onBattleGroundResult`, return via `requestLeaveDynamicSpace` |

**Build 617289 notes:** Runtime logs show `local-ver: 610637.617289` ([script_log_lobby.txt](../../script_log_lobby.txt)). The gateway pins lobby clocks to **2022-04-20** (`GAME_DATE`) so season and shop date gates behave like the late service era ([LOBBY_FINDINGS.md](LOBBY_FINDINGS.md)).

---

## 2. Main lobby and account functions

| Feature | Function |
|---------|----------|
| Login | Authenticate (guest, NetEase, social SDKs) |
| Server selection | Region / server list entry |
| Character | Avatar model, outfit, cosmetics in hall |
| Profile | Name, ID, level, statistics |
| Game mode | Battle modes from lobby UI |
| Team | Invite, join, leave squad |
| Friends | Search, add, lists |
| Inventory | Owned cosmetics and currencies |
| Shop | Mall, supply crates, top-up |
| Events | Missions, seasonal panels |
| Mail | Notices and attachments |
| Leaderboard | Force / wins / kills ranks |
| Settings | Graphics, sound, controls |

**Build 617289 notes**

- **Economy tables:** [mall_goods.json](../server/extract/mall_goods.json) (1160 goods), [pay_goods.json](../server/extract/pay_goods.json) (IAP packs), [supplement_props.json](../server/extract/supplement_props.json) (crate loot).
- **Lobby entity:** `Athlete` with ~1700 exposed base methods ([athlete_base_exposed.json](../server/extract/athlete_base_exposed.json)); the gateway answers a growing subset via [athlete_requests.py](../server/athlete_requests.py).
- **Appearance:** Slot rules in [appearance_slots.json](../server/extract/appearance_slots.json); hall props in [hall_props.json](../server/extract/hall_props.json).
- **Notices:** Changelog strings for Ghillie Island, Fearless Fiord, ranked/casual split in [notice_pc_hw.txt](../../real/notice_pc_hw.txt) (and `.bak`).

**Private server (summary):** Login, server list, shop buys, supply draws, gender/wardrobe, leaderboards, top-up grant, and partial profile/inventory are **partial → working**. Friends, mail, and full event pages remain **stub/none**. See matrix category `Account_and_Lobby`.

---

## 3. Game modes and matchmaking

| Mode | Description |
|------|-------------|
| Solo | One player per team |
| Duo | Two-player teams |
| Squad | Four-player teams (typical) |
| Ranked | Competitive rating |
| Casual | Non-ranked where offered |
| Special / LT | Limited-time rule sets in notices |
| Custom rooms | Private matches where supported |

**Matchmaking steps:** select mode → form party → ready → search → assign session → load map / waiting → countdown → aircraft.

**Build 617289 notes**

- Lobby START flow: `getOpenMaintenanceFightTipFlag` → `createHallTeam(mode)` → `getReadyForBattleGround()` → `matchBattleGround(1)` ([LOBBY_FINDINGS.md](LOBBY_FINDINGS.md) §19–20).
- Default test path uses **Ranked mode 4**, **solo team**, **map group 1** (`DtsMapBaseType.MAP_4K` → battle **map 700**).
- `BattleMatchState`: NONE 0, MATCHING 1, ENTERING 2, PRE_ENTERING 3 — drives `UIBattleGroundsMatchTimer`.

**Private server:** Matchmaking UI through ENTERING and handoff to map 700 is **partial**; true room assignment, prep zone, and multi-player queues are not emulated.

---

## 4. Aircraft, parachute, and landing

| Function | Behavior |
|----------|----------|
| Aircraft route | Jet crosses the island |
| Map preview | Flight path on map / minimap |
| Jump | Leave aircraft in jump window |
| Freefall | Steer descent, speed HUD |
| Parachute | Open canopy, slower descent |
| Landing | On-foot locomotion |

**States:** `IN_AIRCRAFT → FREEFALL → PARACHUTING → LANDED → ACTIVE` (mapped to `fallPhase`, `battleState`, `Plane` attachment).

**Build 617289 notes**

- `BattleGroundGameStatusEnum`: READY 0, PREPARE 1 (~80 s on map 700), BEFORE_FIGHT 2, FIGHT 3, END 4.
- `Plane`: `movePath`, `moveSpeed`, `mode` PEOPLE (1); server drives position via **detailedPosition** (0x58, 30-byte layout) — client `AvatarFilter` does not simulate flight locally.
- Jump: cell `requestGetOffPlane()`; parachute button triggers client `changeFallPhase(5)`.

**Private server:** As of LOBBY_FINDINGS §22–25, **full drop verified** on LDPlayer (countdown → flying jet → jump → skydive → canopy → land). **Plane route streaming** and **team landing** are partial or absent.

---

## 5. Character movement and controls

Standard mobile BR controls: virtual stick, camera zone, fire, ADS, stance buttons, sprint, interact, vehicle enter/exit.

**Conditions:** stand, crouch, prone, swim, vehicle, knocked down (`Wounded`), eliminated (`Died`), parachute (`Parachute`).

**Build 617289 notes:** Pose changes use `changePose(INT8)` → property `pose`. Jump uses `jumpStart` / `jumpEnd`. Most locomotion is **client-authoritative**; the server logs position bundles (msg 2 and 0xBC/0xBD) for drop phase logic.

**Private server:** Crouch/prone **partial**; movement reconciliation **stub/none**.

---

## 6. Weapons and shooting

**Categories:** AR, SMG, shotgun, sniper, DMR, LMG, pistol, melee, throwables, mode-specific specials.

**Attributes:** damage, fire rate, magazine, reload, recoil, spread, range, attachments.

**Build 617289 notes:** [battle_props.json](../server/extract/battle_props.json) and [battle_prop_types.json](../server/extract/battle_prop_types.json) (411 world prop ids). Equipped weapons use `dtsWeapon1..N`, `dtsCurWeapon`, `BATTLE_GROUND_WEAPON_ITEM` structures.

**Private server:** Pickup → bag / auto-equip gun **partial**; fire, reload, hit detection, and PvP damage **none/stub**.

---

## 7. Health, damage, knockdown, elimination

Armor slots (`dtsHelmet`, `dtsVest`), healing consumables, solo instant elimination vs squad knockdown + revive.

**Build 617289 notes:** `hp`, `maxHp`, `actualHP` on `BattleGroundAvatar`. Zone damage table from `maps_utils.getBattleGroundParamData(700)` — eight stages with `DAMAGE` and `INTERVAL` ([battle_flow.py](../server/battle_flow.py) `ZONE_DAMAGE`).

**Private server:** Zone damage to death **partial** (no result screen). Knockdown/revive **none** (solo path). Gun damage **none**.

---

## 8. Loot and inventory

World spawns, pickups, backpack capacity, attachments, airdrops, dead-player crates.

**Build 617289 notes:** World entities `DtsProp` with `propID`, `amount`, `mapID`. Pickup: `tryPickUp` → `onAddDtsItem` (not `onAddItem`).

**Private server:** Manual `loot` spawn and nearby pickup **partial**; map-wide loot tables and drop-from-bag **none**.

---

## 9. Map, safe zone, survival

**Known maps (service era):** **Ghillie Island** (primary 4k BR, **map id 700** in this repo’s tests) and **Fearless Fiord** (larger mode — referenced in notices, not wired in gateway defaults).

| Map function | Purpose |
|--------------|---------|
| World / minimap | Orientation, zone rings |
| Safe zone | Shrinking playable area |
| Zone damage | HP drain outside blue circle |

**Build 617289 notes:** Initial blue circle on 700: centre **(-7507, -4674)**, radius **32000**; eight shrink stages in `battle_flow.ZONE_STAGES`. Client animates with `BattleGroundSpace.updateBlueCircle`; server sends interpolated centres about once per second while shrinking.

**Private server:** Zone shrink **partial** (verified on minimap); full-map UI circles and notify toasts **open**. See LOBBY_FINDINGS §24.

---

## 10. Vehicles and transportation

Cars, bikes, boats (e.g. speedboat in patch notes), fuel and damage on applicable types.

**Build 617289 notes:** `LandCraft` entity definitions in [extract/entities](../server/extract/); `PlayerState.InVehicle` (5).

**Private server:** **none** — no vehicle spawn or drive simulation.

---

## 11. Team, friends, communication

Party in lobby, teammate markers, voice (`ui.chat.voiceUtils`), quick chat, revive, spectate.

**Build 617289 notes:** Voice and CC hosts patched in [CLIENT_DECOMPILE.md](CLIENT_DECOMPILE.md).

**Private server:** Solo-focused; friend lists return empty arrays; voice **none**.

---

## 12. Combat HUD and interface

Joystick, fire, ADS, stance, reload, weapon slots, backpack, heal, minimap, alive/kill counters, team panel, zone timer.

In-match HUD loads with `BattleGroundAvatar` / `PlayerAvatar` after map load (map 700 ~15–40 s on LDPlayer).

---

## 13. Match ending, victory, and results

Last player/team wins; others get placement, kills, survival time, GP/exp rows on `onBattleGroundResult`.

**Build 617289 notes:** Payload shape documented in [battle_flow.py](../server/battle_flow.py) `result_call` (pickle dict per gid, banner ids 7/9/10).

**Private server:** Encoding **stub**; zone death does not yet call `onBattleGroundResult` / `onBattleGroundDie`. Quit-to-lobby handlers exist but are not fully verified post-match.

---

## 14. Progression, cosmetics, meta

Profile level, ranked seasons, daily sign-in, achievements, skins, mall, currencies (gold, diamonds), mail.

**Build 617289 notes:** Season 21 window ended **2022-05-24** in client data; device clock must be in 2022 for some UI (or use `GAME_DATE` + emulator date).

**Private server:** Daily sign-in, mall, diamonds, leaderboard **partial**; season progression grants **stub**.

---

## 15. Full function inventory (74)

Checklist aligned with [gameplay_function_ids.yaml](gameplay_function_ids.yaml). Status summary from [gameplay_function_matrix.json](gameplay_function_matrix.json) (regenerate after editing [gameplay_matrix_evidence.yaml](gameplay_matrix_evidence.yaml)):

| Category | Count | Typical `server_status` |
|----------|-------|-------------------------|
| Account_and_Lobby | 11 | mixed partial/working |
| Matchmaking | 7 | partial / stub |
| Aircraft_and_Landing | 6 | partial / working (jump) |
| Movement_and_Camera | 10 | mostly client-only |
| Weapons_and_Combat | 10 | stub / none |
| Health_and_Inventory | 10 | partial pickup, zone damage |
| World_and_Vehicles | 10 | zone partial; vehicles none |
| Team_and_Results | 10 | leaderboard partial; in-match none |

Use the JSON matrix for the authoritative per-row `client_evidence`, `server_touchpoints`, and `blockers`.

---

## 16. Version caveat

| Question | Answer for this repo |
|----------|----------------------|
| Which APK? | **1.610637.617289** from APKPure XAPK documented in [game/README.md](../../game/README.md) |
| Exact shutdown-day binary? | Not guaranteed; treat regional drift as possible |
| What is verified? | Matrix `confidence: confirmed_build` rows + LOBBY_FINDINGS harness notes |
| What is lore? | Rows marked `generic_br_lore` or `inferred_from_notice` only |

Original commercial service ended **2022-06-27**; this project emulates enough of the stack for preservation and incremental play on a private gateway (Mercury **UDP :25000**, HTTP mocks — see root [README.md](../../README.md)).
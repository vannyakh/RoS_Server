# Rules of Survival — Mobile Restoration Status

**Generated:** 2026-11-26 · **Source:** code inspection + existing LDPlayer notes · **Authority:** CTO

This tracker is for the **original Android client** path (`bigworld_gateway/` + `/api/v1/gateway`). The FastAPI JSON WebSocket stack in `app/` is a parallel control plane and local simulator. It is **not** original-client compatibility.

**Statuses**

| Status | Meaning |
| --- | --- |
| `NOT_CHECKED` | No code or device pass recorded for this row |
| `MISSING` | No implementation on the inspected path |
| `BROKEN` | Implementation exists but fails on the client or server |
| `PARTIAL` | Some behavior exists; gaps remain |
| `IMPLEMENTED` | Code path exists without a fresh mobile re-test in this session |
| `VERIFIED` | Passed on the original APK in LDPlayer (or authorized device) with evidence |
| `BLOCKED` | Waiting on another task, environment, or unknown protocol |

`VERIFIED` requires a mobile test with screenshots or logs. Historical emulator notes from `bigworld_gateway/docs/LOBBY_FINDINGS.md` raise a row to `IMPLEMENTED` or `PARTIAL` only. They do not count as `VERIFIED` until re-run.

Related docs: [GAMEPLAY_FUNCTION_AUDIT.md](GAMEPLAY_FUNCTION_AUDIT.md) · [GAME_FUNCTIONS.md](GAME_FUNCTIONS.md) · [PROTOCOL_MAPPING.md](PROTOCOL_MAPPING.md) · [RESOURCE_MAPPING.md](RESOURCE_MAPPING.md) · [KNOWN_ISSUES.md](KNOWN_ISSUES.md) · [TEST_REPORT.md](TEST_REPORT.md) · [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) · [LOBBY_FINDINGS.md](../bigworld_gateway/docs/LOBBY_FINDINGS.md)

---

## Tracker summary

| Metric | Value |
| --- | --- |
| Checklist items | 132 |
| Verified (mobile) | **2** (checklist rows; not full 132) |
| Implemented (code / historical) | ~38 |
| Partial | ~42 |
| Missing / broken / blocked / not checked | remainder |
| Overall verified | **0%** (0 / 132) |

**Current milestone focus:** Phase 09 **Solo BR first playable** (Start → 9 bots → plane → parachute → land). See [SOLO_GAMEPLAY_STATUS.md](SOLO_GAMEPLAY_STATUS.md). Framing (RO-056) and MatchSession (RO-058) are done; **RO-059** encoders and **RO-057** C2S research are the assigned critical path. Proposed solo params (1+9 bots, warmup, maps) stay unverified.

**Architecture rule:** Prefer repairing `bigworld_gateway/` handlers and `app/api/v1/gateway` persistence. Do not rebuild the working FastAPI control plane. Do not invent Mercury opcodes.

---

## Priority systems (P0–P3)

| Priority | System | Code status | Mobile verified | Next work |
| --- | --- | --- | --- | --- |
| P0 | Authentication | `IMPLEMENTED` Mercury login + SDK forge + gateway resolve | No | Re-run login→hall; document reconnect |
| P0 | Player | `IMPLEMENTED` character, portrait, credit screens | No | Persist outfit; re-test male/female models |
| P0 | Lobby | `IMPLEMENTED` `_lobby_data_calls` + enterHall | No | LDPlayer inactivity / hall.scn load |
| P0 | Matchmaking | `PARTIAL` solo fake match; no shared queue | No | Multi-seat allocation after battle world works |
| P0 | Battle | `PARTIAL` map 700 entry; framing+seam done; no space/plane/bots yet | No | **RO-059 → RO-061 → RO-062 → RO-063 → RO-068/069** (Solo first playable) |
| P1 | Depot | `PARTIAL` buy / equip / try-on | No | Durable ownership end-to-end |
| P1 | Workshop | `PARTIAL` RO-096/097 done in tests; RO-098 LDPlayer pending | No | QA approve 097 → in-game Thunder (RO-098) |
| P1 | Store | `PARTIAL` mall query/buy + listing overrides | No | Sandbox top-up only |
| P1 | Supply | `IMPLEMENTED` draw path + extract JSON | No | Monthly Supreme clock coupling |
| P1 | Social | `MISSING` `getFriendList` unanswered | No | Friends after lobby stability |
| P2 | Events / ranking / missions / mail / custom room | Mostly `MISSING` or `PARTIAL` stubs | No | After P0 battle |
| P3 | Premium / top-up / replay | Stub or admin-only | No | Dev fixtures only; no real payments |

---

## Checklist (132)

### 1. Authentication & Player — 0/9 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 1.1 | Account login and registration | `IMPLEMENTED` | `loginapp.py`, `GatewayService.resolve`, JSON auth routes |
| 1.2 | Guest login | `PARTIAL` | Device uid provision; shared fallback risk |
| 1.3 | Character creation | `IMPLEMENTED` | `createCharacter`, `hero_rules.normalize_hero` |
| 1.4 | Male and female character selection | `PARTIAL` | char 20001 male works historically; female not re-verified |
| 1.5 | Default character appearance | `PARTIAL` | Starter outfit push; empty appearance lists caused UI aborts historically |
| 1.6 | Player nickname and avatar | `PARTIAL` | Nickname + portrait fields; FilePicker HTTP incomplete |
| 1.7 | Player level and experience | `PARTIAL` | Level readable; match-driven EXP not wired from gateway battle end |
| 1.8 | Account data persistence | `IMPLEMENTED` | `gateway_identities` / items via `/api/v1/gateway` |
| 1.9 | Reconnect and session recovery | `PARTIAL` | Mercury/BaseApp keepalives; inactivity drops on LDPlayer |

### 2. Main Lobby — 0/11 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 2.1 | Lobby initialization | `IMPLEMENTED` | `_lobby_data_calls` before `enterHall` (LOBBY_FINDINGS) |
| 2.2 | 3D character rendering | `PARTIAL` | Hall hero after load; appearance table gaps |
| 2.3 | Equipped clothing synchronization | `PARTIAL` | `equipAppearance` session replies; durable outfit via API |
| 2.4 | Weapon display | `NOT_CHECKED` | Hall weapon show path not audited this session |
| 2.5 | Vehicle display | `PARTIAL` | Hall vehicle equip handlers exist |
| 2.6 | Lobby theme | `PARTIAL` | `hallThemeID` required non-zero in team member |
| 2.7 | Background music | `NOT_CHECKED` | Client-local |
| 2.8 | Game mode selection | `PARTIAL` | `createHallTeam(mode)` accepted; modes not fully mapped |
| 2.9 | Map selection | `PARTIAL` | Map group → map 700 hardcoded path |
| 2.10 | Server and region selection | `PARTIAL` | Forged server list / DNS to LAN PC |
| 2.11 | Start matchmaking | `VERIFIED` | RO-108 `to_match.sh` → full START chain in gateway log |

### 3. Depot & Inventory — 0/11 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 3.1 | Open Depot UI | `PARTIAL` | Historical; left-menu abort history |
| 3.2 | Owned item list | `PARTIAL` | Session grants + gateway items |
| 3.3 | Item ownership persistence | `PARTIAL` | `GatewayItem` / purchase API |
| 3.4 | Equip appearance | `IMPLEMENTED` | `equipAppearance` replies |
| 3.5 | Unequip / swap | `NOT_CHECKED` | |
| 3.6 | Body / wearable slots | `PARTIAL` | Show body vs wearable lists |
| 3.7 | Try-on | `PARTIAL` | Try-on handlers present |
| 3.8 | Buy from Depot prices | `IMPLEMENTED` | `buyDtsHallProp` + `hallprop_prices.json` |
| 3.9 | Currency charge on buy | `PARTIAL` | Diamond (`onYBUpdated`) |
| 3.10 | Inventory quantity / stacks | `PARTIAL` | Battle bag separate from hall |
| 3.11 | Cross-login ownership | `PARTIAL` | Needs fresh mobile persistence check |

### 4. Workshop — 0/8 verified

Active engineering track: **RO-095** (research, review) · **RO-096** / **RO-097** (in progress) · **RO-098** (LDPlayer) · **RO-099** (other categories).

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 4.1 | Open Workshop UI | `PARTIAL` | Client UI exists; server compound path under RO-097 |
| 4.2 | Skin evolution | `PARTIAL` | `appearanceCultivateCompound` research (RO-095); handler WIP |
| 4.3 | Remodel | `NOT_CHECKED` | Separate from cultivate compound |
| 4.4 | Material consumption | `PARTIAL` | Spec in RO-095; atomic API in RO-096 |
| 4.5 | Evolution level persist | `PARTIAL` | Gateway items / compound WIP |
| 4.6 | Vehicle / firearm / companion cultivate | `PARTIAL` | Vehicle chains first; others RO-099 |
| 4.7 | Aircraft cultivate | `NOT_CHECKED` | |
| 4.8 | Clothes remodel | `NOT_CHECKED` | |

### 5. Store & Economy — 0/10 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 5.1 | Mall goods query | `IMPLEMENTED` | `queryAvailableMallGoods*` |
| 5.2 | Buy mall good | `IMPLEMENTED` | `buyMultipleMallGood` / related |
| 5.3 | Store listing overrides | `IMPLEMENTED` | Alembic `c8f3a5d27e14`, admin store |
| 5.4 | Free / pay yuanbao display | `IMPLEMENTED` | `onYBUpdated` |
| 5.5 | VIP info for UI | `PARTIAL` | `syncVipInfo` at login |
| 5.6 | Supply boxes | `IMPLEMENTED` | supplement extract + open handlers |
| 5.7 | Free lottery timestamp | `IMPLEMENTED` | |
| 5.8 | Monthly Supreme Supply | `BROKEN` | Device clock vs dated monthly IDs |
| 5.9 | Real payment / IAP | `MISSING` | Dev fixtures only (policy) |
| 5.10 | Transaction history | `PARTIAL` | Inventory transactions in `app/`; gateway incomplete |

### 6. Matchmaking & Game Room — 0/10 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 6.1 | Create hall team | `IMPLEMENTED` | Solo `onEnterHallTeam` |
| 6.2 | Ready for battleground | `IMPLEMENTED` | `syncReadyState` + `syncMatchState` |
| 6.3 | Match battle ground | `VERIFIED` | RO-108 log: `matchBattleGround` → ENTERING → `resetEntities` (2026-11-26) |
| 6.4 | Cancel match | `IMPLEMENTED` | `cancelMatchBattleGround` |
| 6.5 | Duo / Squad party | `MISSING` | One-member team only |
| 6.6 | Shared matchmaking queue | `MISSING` | Instant fake match |
| 6.7 | Custom room create/join | `PARTIAL` | `createDtsCustomGame` stub |
| 6.8 | Room configuration | `MISSING` | |
| 6.9 | Multi-player same match instance | `MISSING` | Per-`addr` `Match()` |
| 6.10 | Pre-match resource checks | `PARTIAL` | Client-side; server answers maintenance tip |

### 7. Battle Gameplay — 0/24 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 7.1 | Enter map / load map 700 | `IMPLEMENTED` | LOBBY_FINDINGS update 4 |
| 7.2 | BattleGroundAvatar create | `IMPLEMENTED` | `avatar_create_messages` |
| 7.3 | createEntity framing (non-player) | `VERIFIED` | RO-056: `BattleGroundSpace` 20001, `circleStage=1` Frida; active port no RESEND after `space` |
| 7.4 | BattleGroundSpace entity | `PARTIAL` | `space` trigger historically; blocked on framing re-proof |
| 7.5 | Plane / boarding | `PARTIAL` | Entity builder; full flight path open (**RO-062**) |
| 7.6 | Jump / parachute / glide / land | `PARTIAL` | Fall phases + position land; voluntary jump open |
| 7.7 | Position sync (0xBC/0xBD) | `MISSING` | Observed, not handled |
| 7.8 | Movement authority | `PARTIAL` | Client-side joystick historically |
| 7.9 | Pose / crouch / prone | `PARTIAL` | `changePose` handled |
| 7.10 | Doors open/close | `PARTIAL` | `openElement`/`closeElement`; coverage incomplete |
| 7.11 | Loot spawn | `PARTIAL` | `DtsProp` spawn path; not map-wide |
| 7.12 | Pickup | `PARTIAL` | `tryPickUp` |
| 7.13 | Discard | `MISSING` | **RO-078/079** |
| 7.14 | Equip weapon slots | `PARTIAL` | Research/tasks open |
| 7.15 | Shooting / reload / damage | `MISSING` | Gateway combat loop absent |
| 7.16 | Healing / armor | `MISSING` | |
| 7.17 | Safe zone damage | `PARTIAL` | Space circle fields; authoritative tick open |
| 7.18 | Vehicles | `MISSING` | Hall only; battle **RO-091/092** |
| 7.19 | Knockdown / revive | `MISSING` | |
| 7.20 | Elimination | `MISSING` | |
| 7.21 | Spectate | `MISSING` | |
| 7.22 | Results screen | `PARTIAL` | Quit-to-lobby historical; win path not wired |
| 7.23 | Match rewards / EXP | `PARTIAL` | `GatewayProfileService.record_match` not driven by battle win |
| 7.24 | Return to lobby | `PARTIAL` | Historical quit path |

### 8. Social & Communication — 0/11 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 8.1 | Friend list | `MISSING` | `getFriendList` → empty |
| 8.2 | Add / remove friend | `MISSING` | |
| 8.3 | Team invitations | `MISSING` | |
| 8.4 | Hall team multi-member | `MISSING` | |
| 8.5 | Chat | `MISSING` | |
| 8.6 | Presence | `PARTIAL` | Gateway presence API |
| 8.7 | Block / report | `NOT_CHECKED` | |
| 8.8 | Clan / club | `NOT_CHECKED` | |
| 8.9 | Invite to custom room | `MISSING` | |
| 8.10 | Spectator invite | `MISSING` | |
| 8.11 | Social rewards | `MISSING` | |

### 9. Events & Progression — 0/10 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 9.1 | Daily sign-in | `PARTIAL` | Athlete sign-in reply; durability weak |
| 9.2 | Limited events | `MISSING` | |
| 9.3 | Ranking / leaderboard | `PARTIAL` | Profile rank fields; no season board |
| 9.4 | Seasons | `MISSING` | |
| 9.5 | Daily missions | `MISSING` | Catalog only in `app/` |
| 9.6 | Weekly missions | `MISSING` | |
| 9.7 | Achievements claim | `MISSING` | Definitions seeded; no claim path |
| 9.8 | Lucky Carnival data | `PARTIAL` | Stub attributes to unblock lobby |
| 9.9 | Red-point / tips | `PARTIAL` | Historical UI abort fixes |
| 9.10 | Maintenance fight tip | `IMPLEMENTED` | `getOpenMaintenanceFightTipFlag` |

### 10. Mail & Rewards — 0/7 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 10.1 | Mailbox list | `MISSING` | |
| 10.2 | Read mail | `MISSING` | |
| 10.3 | Attachments | `MISSING` | |
| 10.4 | Claim rewards | `MISSING` | |
| 10.5 | Credit / battle pass claim | `PARTIAL` | Credit claim API / athlete queries |
| 10.6 | Match history UI | `PARTIAL` | Profile screens + API |
| 10.7 | Announcement notices | `PARTIAL` | Static notice HTTP |

### 11. Custom Room & Settings — 0/11 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 11.1 | Create custom room | `PARTIAL` | Stub handler |
| 11.2 | Join custom room | `MISSING` | |
| 11.3 | Room password | `MISSING` | |
| 11.4 | Map / mode config | `MISSING` | |
| 11.5 | Bot fill | `MISSING` | Gateway |
| 11.6 | Start from custom room | `MISSING` | |
| 11.7 | Client graphics settings | `NOT_CHECKED` | Device-local |
| 11.8 | Sensitivity / controls | `NOT_CHECKED` | |
| 11.9 | Account settings sync | `MISSING` | |
| 11.10 | Language | `NOT_CHECKED` | |
| 11.11 | Privacy settings | `MISSING` | |

### 12. Persistence & Stability — 0/10 verified

| # | Function | Status | Evidence |
| --- | --- | --- | --- |
| 12.1 | Gateway → FastAPI link | `IMPLEMENTED` | `account_link.py` |
| 12.2 | Offline local fallback | `PARTIAL` | `saved_accounts.json` |
| 12.3 | No negative currency | `PARTIAL` | App constraints; gateway draw charge path |
| 12.4 | Idempotent grants | `PARTIAL` | Needs mobile regression |
| 12.5 | Unauthorized equip blocked | `PARTIAL` | Ownership gaps noted in audit |
| 12.6 | Migration safety | `IMPLEMENTED` | Alembic head `c8f3a5d27e14` |
| 12.7 | Structured gateway logs | `PARTIAL` | Athlete name logging |
| 12.8 | LDPlayer automation | `PARTIAL` | `to_match.sh`, `setup_emulator.ps1` |
| 12.9 | Protocol inspector tooling | `PARTIAL` | Frida payloads; not full battle matrix |
| 12.10 | Process stability (no RESEND loop) | `PARTIAL` | Malformed createEntity caused RESEND historically |

---

## Server map (existing, do not rebuild)

```text
app/                          # FastAPI control plane + JSON match sim
app/api/v1/gateway.py         # Persistence for original client
bigworld_gateway/server/
  loginapp.py                 # Mercury login
  ros_server.py               # HTTP forge + UDP BaseApp + Athlete handlers
  athlete_requests.py         # 1191 Athlete base method names
  battle_flow.py              # Match entities + limited battle RPCs
  account_link.py             # Calls /api/v1/gateway
  profile_screens.py
  extract/                    # Client tables (not invented opcodes)
```

Proposed `modules/` tree from the restoration brief maps onto these paths. Prefer extending handlers here over a greenfield layout.

---

## Execution queue (CTO)

1. **Done:** audit (**RO-100**), START handoff (**RO-107**), createEntity live proof (**RO-056**), START logs (**RO-108**).
2. **Now (match P0):** assign **RO-059** — verified createEntity encoders in `battle_flow.py`.
3. **Workshop (P1):** **RO-097** in review; **RO-098** Thunder LDPlayer when deps closed.
4. **Next:** **RO-058** session seam, **RO-057** battle request map, plane/loot/doors.
5. **Do not prioritize** React admin until P0 match gameplay is mobile-verified.

---

## Registry links

| Registry | Path |
| --- | --- |
| Tasks | `.cursor/management/tasks.json` |
| Milestones | `.cursor/management/milestones.json` |
| Compatibility | `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` |
| Gap review | `docs/engineering/GATEWAY_MATCH_GAP_REVIEW.md` |

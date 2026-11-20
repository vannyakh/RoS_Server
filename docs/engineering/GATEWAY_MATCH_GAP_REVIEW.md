# Gateway match gap review

Date: 2026-11-19. Author: CTO. Scope: what the original-client gateway (`bigworld_gateway/`) and the FastAPI side do for an in-game match, against the list the owner gave. Code was read, not run. No emulator, no gateway start. Status words: implemented (works on the emulator per `bigworld_gateway/docs/LOBBY_FINDINGS.md`), partial (code or data exists but the feature is not visible in-game), missing.

Nothing here is original-server compatibility. Every row stays `unknown` or `researching` until a reviewed task says otherwise.

## Summary

The gateway takes the player from START to a loaded map 700 as a `BattleGroundAvatar`, and stops there. The client then sees the HUD, minimap and a fist weapon, and nothing else: no space entity, no plane, no props, no doors, no bots, no end of match. All six items the owner listed are missing in-game.

One blocker is shared. `createEntity` property data is not framed correctly, so no non-player entity (`BattleGroundSpace`, `Plane`, `DtsProp`, `Robot`) can be created on the client (`bigworld_gateway/docs/LOBBY_FINDINGS.md:121-123`). The second gap is on the receive side: while a match runs, the gateway decodes no client request, so the OPEN button press is never answered.

## Table

| Function | State | Evidence | Blocker | Owner task |
| --- | --- | --- | --- | --- |
| START, team, matching timer, ENTERING, hand-off to `BattleGroundAvatar` on map 700 | implemented | `bigworld_gateway/server/ros_server.py:1561-1583` (`createHallTeam`, `matchBattleGround`), `:1837-1848` (`_enter_battle`), `:475-525` (`avatar_create_messages`); `LOBBY_FINDINGS.md:73-78` | none | done (no task) |
| Debug trigger for message experiments (`space`, `space0`, `ce`, `leave`, `raw`) | implemented | `ros_server.py:1159-1173`, `bigworld_gateway/server/battle_flow.py:138-165` | none | done |
| Create a non-player entity (`enterAoI` + `createEntity`) | partial | `battle_flow.py:91-120` builds the message; the client creates the entity then fails in `enterWorld` because property values do not arrive; `LOBBY_FINDINGS.md:121-122`; `CE_PROPS`, `CE_PREFIX`, `CE_INDEX`, `CE_DIR` switches at `battle_flow.py:63,96,102,118` are guesses | property-data framing unsolved (flag byte, compression type, stream layout) | RO-056 (research), RO-059 (encoder) |
| Property update and entity method call on a non-player entity | missing | `battle_flow.py:7-8` marks `0xC0\|idx` and `0x80\|idx` "unverified on this client"; no builder exists | RO-056 | RO-059 |
| A bad `createEntity` kills the channel | known risk | `LOBBY_FINDINGS.md:123` (`BASEAPP RESEND` forever, restart needed) | tests must use captured bytes | RO-059 |
| Decode client requests during a match (OPEN, pickup, jump, parachute, position) | missing | `ros_server.py:1187-1192` runs the Athlete decoder only when `_in_battle` is not set; `LOBBY_FINDINGS.md:77` (position messages `0xBC`/`0xBD` "not handled yet"); no cell-method table like `server/extract/athlete_base_exposed.json` | exposed cell-method ids not dumped | RO-057 (research), RO-060 (decoder), RO-058 (seam) |
| Battle code structure | partial | all inline in `ros_server.py` (2188 lines); one `trigger_battle.txt` hook | later tasks would collide on `ros_server.py` | RO-058 |
| (4) Pre-start countdown / training | missing | `LOBBY_FINDINGS.md:78` ("120 LEFT" is the client default); space props `gameStartTime`, `gameStatus`, `clientStatus`, `aliveNum` exist in `bigworld_gateway/server/extract/entities_out/150_3a9801e3.bin` (`defs\battlegroundspace.def`) but are never sent; the JSON simulator has a countdown phase (`app/game/rules.py:15`, `app/game/simulate.py:237`) that is not connected to the gateway | needs the space entity (RO-059); values and HUD trigger are not known | RO-061 |
| (5a) Plane and boarding | missing | `Plane` is client type 147 (`bigworld_gateway/server/extract/client_entity_types.json`); props `movePath`, `moveSpeed`, `inJumpArea`, `mode`; `battle_flow.py:134-135` reserves an id only; spawn is `0,0,0` on the ground (`ros_server.py:521`, `LOBBY_FINDINGS.md:78`) | entity creation (RO-059) | RO-062 |
| (5b) Jump, parachute, glider, landing | missing | exposed methods exist in the defs: `requestGetOffPlane` (`entities_out/099_25abc9c1.bin:280`, `iBattleGround`), `chooseParachute` and `chooseGlider` (`entities_out/064_166905e1.bin:115-119`, `iJetWingsAvatar`); the gateway answers none; JSON simulator `app/game/simulate.py:586` is separate | request decoder (RO-060), plane (RO-062) | RO-063 |
| (6) Shrinking safe zone | partial | `battle_flow.py:150-156` (`space` command) sets one static circle through the unsolved property path; `BattleGroundSpace` has `circleStage`, `whiteCircle*`, `blueCircle*`, client methods `onRequestCircleRestTime`, `updateCircleRestTime`, `showCircleNotify` (`150_3a9801e3.bin:610-652`); nothing is staged over time; JSON simulator `app/game/rules.py:19-20`, `simulate.py:285-312` is not reachable by the gateway | property update (RO-059), player position (RO-060/063) | RO-064 |
| (2) Loot, DtsProp entities, pickup | missing | `DtsProp` is client type 140 (10 client props: `propID`, `amount`, `info`, `groupID`, ...); no gateway code references it; loot data for the original does not exist in the repo; `app/game/items.py:55-67` `LOOT_TABLE` is a JSON-simulator table with ids like `rifle`, not original prop ids | loot layout and prop id source unknown; pickup request layout unknown | RO-065 (research), RO-066 |
| (1) Doors: OPEN button | missing | doors are `BattleGroundSpace` map elements: exposed cell methods `openElement(INT32 elemID, INT8 state)` and `closeElement(INT32 elemID)` (`150_3a9801e3.bin:790-796`), client methods `onElementOpen`, `onElementClose` (`:627-633`), property `openedElements` ARRAY of `DTS_ELEMENT {elemID, state}` (`:286-289`, alias in `640_ea6b2959.bin:3898-3907`); the gateway has no handler for any of them (`grep` of `bigworld_gateway/server/*.py` finds no `openElement`); `app/` has no door concept (`grep -ri door app` is empty) | request decoder (RO-060), space entity (RO-059/061); RO-057 must confirm the client really calls `openElement` | RO-067 |
| (3) Bots | missing | `Robot` is client type 58 (125 client props); no gateway code creates one; the JSON simulator has bots (`app/game/simulate.py:188-197,389`, `app/game/rules.py:13`) that never reach the original client | which entity and which properties render a bot; movement sync layout | RO-068 (research), RO-069 |
| Death, result screen, return to lobby | missing | no death or result handling in `ros_server.py`; the only path back to the lobby is `_transition_to_athlete` on the tutorial SKIP request (`ros_server.py:1177`, `:2019`); `LOBBY_FINDINGS.md:78` ("no death or results screen, no return to the lobby") | RO-064 for zone death; result method names unknown | RO-071 |
| Report the match to RoS_Server | partial | route exists: `POST /api/v1/gateway/accounts/{uid}/matches` (`app/api/v1/gateway.py:121-131`, `app/services/gateway_profile_service.py:64`, schema `GatewayMatchReport` in `app/schemas/gateway.py:150`); the gateway never calls it (`bigworld_gateway/server/account_link.py` has `get_profile` at `:217` and no `record_match`) | none; the route has no match id, so a retry would double count | RO-070 |
| Match state, loot tables, bot settings in FastAPI | not needed for now | `app/game/engine.py` and `app/game/simulate.py` run the JSON-protocol simulator on a 200x200 test map; the gateway is a separate process and must not import `app/` (`AGENTS.md`); coordinates and item ids do not match the original client | decision: match state stays gateway-local | RO-058 (design note) |

## What the FastAPI side needs

Short answer: nothing new for items 1 to 6.

- Match results: the route exists (profile tests in `tests/integration/test_gateway_profile.py`), but the gateway side is missing (RO-070). The route has no idempotency key. RO-070 sends one report per match with no retry. A real idempotency key needs a table and a migration, which needs the database and migration owners; it is not tasked yet.
- Loot tables, bot count, zone stages: keep them as gateway data files (`bigworld_gateway/server/battle/data/*.json`, RO-061, RO-064, RO-066, RO-069). An admin-editable configuration route can be added later. It would be a new contract and needs code, tests, and `docs/API_CONTRACT.md` in the same change.
- Match state: the gateway keeps it in memory for the match. The database sees only the final report, as `AGENTS.md` requires.

## Order and dependencies

```text
RO-056 framing research (ready, critical) -> RO-059 entity encoders
RO-057 request-id research (ready)         -> RO-060 request decoder, RO-065 loot research
RO-058 battle session seam (ready)         -> RO-060, RO-061, RO-070
RO-059 + RO-058 -> RO-061 space + countdown -> RO-062 plane -> RO-063 jump (also RO-060) -> RO-064 zone
RO-059 + RO-060 + RO-061 + RO-065 -> RO-066 loot and pickup
RO-059 + RO-060 + RO-061 -> RO-067 doors
RO-056 + RO-057 -> RO-068 bot research; RO-059 + RO-063 + RO-068 -> RO-069 bots
RO-058 -> RO-070 match report; RO-064 + RO-070 -> RO-071 death, results, return to lobby
RO-066 + RO-067 + RO-069 + RO-071 -> RO-072 QA acceptance; RO-066 + RO-067 -> RO-073 security review
```

Three tasks have no open dependency (RO-056, RO-057, RO-058) and are `ready`. Each assignee runs its own session; `files_allowed` do not overlap, so all three can run in parallel (`game-compatibility-engineer` runs one at a time, so RO-056 goes first). All other tasks are `backlog`. No task is assigned, in progress or completed.

Door work (RO-067) and loot work (RO-066) do not depend on the plane or the zone, only on the space entity and the request decoder. A player can therefore see doors and props before the full flight sequence works, if the owner wants that order.

## File ownership

`bigworld_gateway/**` was in no agent's `allowed_paths`. `team.json` now grants:

- game-compatibility-engineer: `bigworld_gateway/docs/**`, `bigworld_gateway/client/frida/**`, `bigworld_gateway/server/extract/**`
- backend-architect: `bigworld_gateway/server/ros_server.py`, `battle/__init__.py`, `battle/session.py`, `tests/compatibility/gateway/session/**`
- protocol-test-engineer: `bigworld_gateway/server/battle_flow.py`, `bigworld_gateway/server/battle/requests.py`
- gameplay-test-engineer: `bigworld_gateway/server/battle/timeline.py`, `battle/modules/**`, `battle/data/**`
- api-engineer: `bigworld_gateway/server/account_link.py`, `docs/API_CONTRACT.md`, `tests/integration/test_gateway_match_report.py`

Only RO-058 edits `ros_server.py`. Later work lands in new files under `bigworld_gateway/server/battle/`, one file per feature, so those tasks do not overlap.

## Risks

- Each in-game check needs the emulator and the original client. The CTO did not run them. Specialists run them and record the log excerpt; the CTO reruns the verification commands before accepting.
- A malformed `createEntity` breaks the channel until the match restarts (`LOBBY_FINDINGS.md:123`). Unit tests must use captured bytes, and RO-059 may not merge a layout that was tried on only one run.
- The client defs name properties, not values. Countdown, zone and plane parameters in this plan are gateway choices, not original values.
- Two agents probing one emulator overwrite each other's payload (`LOBBY_FINDINGS.md:105`). Run the in-game checks one at a time.

## Interaction gaps (second owner request, 2026-11-19)

Scope: doors, loot quantities, discard from the bag, breakable glass, character actions and weapon equip. Code and docs were read, not run. No emulator, no Frida, no gateway start. This section supersedes the "(1) Doors" and "(2) Loot" rows above where they say the request decoder is missing: other teams added a first pass in `bigworld_gateway/server/battle_flow.py` (`decode_request` `:254`, `Match.handle` `:283`, called from `bigworld_gateway/server/ros_server.py:1172-1178`) and recorded it in `LOBBY_FINDINGS.md` updates 10 and 11. That code sits in the file RO-059 owns and in `ros_server.py` (RO-058). The new tasks therefore add files under `bigworld_gateway/server/battle/` and do not edit `battle_flow.py`. State words as above.

Paths `entities_out/...` are under `bigworld_gateway/server/extract/`.

| Function | State | Evidence | Blocker | Owner task |
| --- | --- | --- | --- | --- |
| (1) Door OPEN button: reply to `openElement(INT32 elemID, INT8 state)` / `closeElement(INT32)` | partial | replies `onElementOpen` / `onElementClose` and the `Match.doors` dict, `battle_flow.py:271,294-300`; request ids `0x88` / `0x89` verified, `LOBBY_FINDINGS.md` update 10; replies for door 832 raise no client error, a visibly opening door was never captured, update 11; defs `entities_out/150_3a9801e3.bin:790-796` (methods), `:286-289` (`openedElements`) | the owner reports some or all buildings fail. Candidate causes, none checked: element id not in the scene lookup; `openedElements` never sent (`LOBBY_FINDINGS.md` update 10: "not used yet"); double doors with two ids; the `state` meaning unknown (the reply echoes `args[:5]`, `battle_flow.py:296`). Door types that send no `openElement` are untested | RO-074 (research), RO-075 (door table), RO-067 (module) |
| (1b) Door state for a joining or recreated client | missing | `openedElements` is not written anywhere in `bigworld_gateway/server/`; `LOBBY_FINDINGS.md:143` "no door state replay" | property-update encoder (RO-056, RO-059) | RO-067 |
| (2a) Loot: weapon items | partial | `DtsProp` spawn with `propID`, `mapID`, `amount` and the pickup reply `onAddDtsItem` + `onPickUpPropEntity`, `battle_flow.py:276-281,301-309`; the test `loot` command uses ids 1001, 1101, 2200, 2300, 1002, 1102, 1301, 1401, `:181`; the package shows the item, `LOBBY_FINDINGS.md` update 11 | no loot table and no building spawn for map 700; weapon `info` dict (attachments, ammo) unknown | RO-065, RO-066, RO-076 |
| (2b) Loot: picked-up quantity, stacks, ammo/heal/armor amounts | partial | the amount goes to `ITEM_DATA_CONVERT.number` (`battle_flow.py:306`) but the test command always spawns amount 1 (`:186`), so every pickup is 1 (`LOBBY_FINDINGS.md` update 11). `DtsProp.amount` is one of 10 client properties (`CREATE_ENTITY_FORMAT.md:125`); folded items use `onDelDtsFoldedItem(ITEM_ID, ITEM_CNT)` (`entities_out/374_88d14d31.bin:80-83`) | stack sizes and default amounts per prop id are not extracted; the add method for folded stacks is untested | RO-076 (research), RO-077 |
| (2c) Partial pickup: `DtsProp.syncAmount(INT32)` and the first `tryPickUp` argument | missing | `syncAmount` is a client method of `defs/dtsprop.def` (`entities_out/592_db694dc4.bin:60-62`); `tryPickUp(INT32, BOOL)` (`:70-73`) is decoded but the first argument is ignored: `battle_flow.py:301-302` removes the whole prop for any value (the client always sent 1, `LOBBY_FINDINGS.md` update 10). No code references `syncAmount` | meaning of argument 1 unknown (slot, count or other) | RO-076, RO-077 |
| (3) Drop an item out of the bag | missing | no handler. Defs: exposed `discardProp(INT32, INT32, STRING)` on `defs/interfaces/idtsprop.def` (`entities_out/182_48835979.bin:96-100`); client replies `onDiscardProp(INT32, INT32)` (`:222-225`), `onDelDtsItem(ITEM_ID, ITEM_UUID)` and `onDelDtsFoldedItem(ITEM_ID, ITEM_CNT)` (`374_88d14d31.bin:75-83`); the space-internal `BattleGroundSpace.discardProp(INT32, INT32, PY_DICT, VECTOR3)` (`150_3a9801e3.bin:742-747`). The server holds no copy of the player's package to remove from: the gateway only sends `onAddDtsItem` | msg id, argument order and client method indices (offsets +2/+3 differ per method, `LOBBY_FINDINGS.md` update 11) unmeasured; package state must live on the server | RO-078 (research), RO-077 (package state), RO-079 |
| (4) Breakable windows and glass | missing | exposed `blastGunShoot(VECTOR3, VECTOR3, VECTOR3, FLOAT, FLOAT)` and `uploadBlastState(INT32, BLOB)` (`entities_out/150_3a9801e3.bin:797-807`), property `blastObjectStates` (`:290-293`, client index 68, `CREATE_ENTITY_FORMAT.md:132`); no gateway code mentions blast. Whether the client needs a reply is unknown; window vault may be client only | request ids and BLOB layout unmeasured | RO-080 (research), RO-081 |
| (5a) Jump, walk, crouch, prone, sit, lean, other actions | missing | exposed `doCommonGameAction(STRING, BOOL, STRING, STRING)`, `doInGameAction(INT32)` (`entities_out/099_25abc9c1.bin:388-396`, `defs/interfaces/ibattleground.def`), `syncLeanState(FLOAT)` (`entities_out/331_7c78ef0b.bin:441-443`, `defs/interfaces/icombatunit.def`), client `onOtherDoInGameAction`, `onOwnDoInGameAction` (`099_25abc9c1.bin:502-509`); the gateway handles none. Walking works on the client only (`LOBBY_FINDINGS.md:77`) | which actions need a server reply or an own-state property update is unknown; own-state updates need RO-056 | RO-082 (research), RO-083 |
| (5b) Player position messages `0xBC` / `0xBD` | missing | `LOBBY_FINDINGS.md:77` ("not handled yet"), `:143` ("logged, not decoded"); `ENTITY_PROPERTY_UPDATE_FORMAT.md:72` says `0xBD` is a no-argument method; `0xBC` is also the low byte of 700 (`CREATE_ENTITY_FORMAT.md:17`) | field layout and units unknown | RO-057 (layout), RO-060 (decode), RO-082 |
| (5c) Equip a picked-up weapon (`dtsWeapon1/2`, `dtsCurWeapon`, `onWearDtsWeapon`) | missing | `LOBBY_FINDINGS.md` update 11 "Weapons picked up are not equipped"; client indices `dtsWeapon1` 423, `dtsWeapon3` 425, `dtsCurWeapon` 431 (`ENTITY_PROPERTY_UPDATE_FORMAT.md:55`) are static analysis, "nothing here was tried on a live client" (`:4`); no property-update builder in `battle_flow.py` | RO-056 must verify the property-update message on the client; slot semantics unknown | RO-056, RO-076 (research), RO-084 |
| Acceptance and review of the above | missing | no tests exist for any of it | all of the above | RO-085 (QA), RO-086 (security) |

### Tasks

Paths in the Files column other than `tests/` and `docs/` are under `bigworld_gateway/`.

| Id | Owner | Status | Depends on | Files (new, no overlap with RO-056..RO-073) |
| --- | --- | --- | --- | --- |
| RO-074 | game-compatibility-engineer | ready | none | `docs/DOORS_AND_ELEMENTS.md`, `client/frida/payloads/doors/**`, `server/extract/map700_elements.json` |
| RO-075 | gameplay-test-engineer | backlog | RO-067, RO-074 | `server/battle/data/doors.json`, `tests/compatibility/gateway/doors_coverage/**` |
| RO-076 | game-compatibility-engineer | backlog | RO-056, RO-065 | `docs/ITEM_QUANTITIES_AND_EQUIP.md`, `client/frida/payloads/quantities/**`, `server/extract/prop_amounts.json` |
| RO-077 | gameplay-test-engineer | backlog | RO-066, RO-076 | `server/battle/modules/items.py`, `server/battle/data/item_amounts.json`, `tests/compatibility/gateway/items/**` |
| RO-078 | game-compatibility-engineer | backlog | RO-057 | `docs/BAG_DISCARD.md`, `client/frida/payloads/discard/**`, `server/extract/discard_methods.json` |
| RO-079 | gameplay-test-engineer | backlog | RO-060, RO-066, RO-077, RO-078 | `server/battle/modules/discard.py`, `tests/compatibility/gateway/discard/**` |
| RO-080 | game-compatibility-engineer | backlog | RO-057 | `docs/BREAKABLE_SCENE.md`, `client/frida/payloads/blast/**`, `server/extract/map700_blast.json` |
| RO-081 | gameplay-test-engineer | backlog | RO-059, RO-060, RO-061, RO-080 | `server/battle/modules/blast.py`, `tests/compatibility/gateway/blast/**` |
| RO-082 | game-compatibility-engineer | backlog | RO-056, RO-057 | `docs/CHARACTER_ACTIONS.md`, `client/frida/payloads/actions/**`, `server/extract/avatar_action_methods.json` |
| RO-083 | gameplay-test-engineer | backlog | RO-059, RO-060, RO-082 | `server/battle/modules/actions.py`, `tests/compatibility/gateway/actions/**` |
| RO-084 | gameplay-test-engineer | backlog | RO-059, RO-066, RO-076, RO-077 | `server/battle/modules/equip.py`, `tests/compatibility/gateway/equip/**` |
| RO-085 | qa-engineer | backlog | RO-075, RO-077, RO-079, RO-081, RO-083, RO-084 | `docs/testing/GATEWAY_INTERACTION_ACCEPTANCE.md`, `tests/regression/test_gateway_interactions.py` |
| RO-086 | security-engineer | backlog | RO-077, RO-079, RO-081, RO-083, RO-084 | `docs/engineering/reviews/RO-086-gateway-interaction-security.md` |

RO-067 gained the dependency RO-074 and a description note. RO-060 and RO-066 are reused as they are: RO-077 and RO-079 call `props.py`, they do not edit it.

Order: RO-074 is `ready` with no dependency and is the first complaint, so it runs first (the game-compatibility engineer runs one task at a time; RO-056 and RO-057 are also ready and unlock most of the rest). Items 3, 4 and 5 need the RO-057 request ids. Everything that sends a property update waits on RO-056 and RO-059. One `game-compatibility-engineer` serves eight research tasks (RO-056, RO-057, RO-065, RO-074, RO-076, RO-078, RO-080, RO-082), so the research queue limits the schedule.

Risks: the `battle_flow.py` first pass was not re-run by the CTO. Client method index offsets (+2 or +3) are measured per method, so each new reply (`onDelDtsItem`, `onDelDtsFoldedItem`, `onDiscardProp`, `syncAmount`) must be tried once on the emulator before a test freezes its bytes. Server-side package state (RO-077) is a second copy of what the client holds; a mismatch lets a player drop an item they do not own, so RO-079 validates against it and RO-086 reviews duplication.

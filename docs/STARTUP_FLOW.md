# Startup flow: login to lobby (original client gateway)

Task RO-101. Evidence only. Covers what `bigworld_gateway/server/ros_server.py` sends to the original Android client between `Account.handshake` and the lobby, how big it is, and how long it takes. Nothing here has been tested on a device as a change. **Do not remove or defer any message without a device test on LDPlayer.**

Reproduce the numbers:

```powershell
.\.venv\Scripts\python.exe bigworld_gateway/tools/startup_trace.py --logs
```

The script builds the real bodies with the gateway's own functions (`athlete_create_message`, `GateUDP._send_enter_hall_calls`, `GateUDP._athlete_request`). It does not open sockets, call the RoS_Server API or read `saved_accounts.json`. It uses the `config.cmd` environment (2022 clock, `FRAG_BODY=700`, `UNLOCK_ALL=off`, `HALL_POPUPS=off`) and a fixed existing account with no owned items.

## Sequence

| Step | Trigger | What the gateway sends | Code |
|---|---|---|---|
| 1 | `Account.handshake` (msg `0xC5`) | `resetEntities(False)` + `createBasePlayer(Athlete)` with all 720 Athlete properties | `ros_server.py` handshake branch (~line 1396), `athlete_create_message()` (~line 956) |
| 2 | `HALL_DELAY` later (3 s in `config.cmd`) | Login bundle: `onLogin`, `onRoleCreateSuc`, two switch calls, then `_lobby_data_calls()` | `_send_enter_hall_calls()` (~line 1617), `_lobby_data_calls()` (~line 2314) |
| 3 | 0.2 s after step 2 | `enterHall(firstLoginToday)` in its own bundle | `_send_enter_hall_calls()` (~line 1669), `_first_login_today()` (~line 805) |
| 4 | Client loads `scene\hall\hall.scn` | Nothing (keepalive ACKs only) | LOBBY_FINDINGS "Slow lobby load" |
| 5 | Client opens Supply (by tap or by a push) | `onQueryAvailableSupplement` (full catalogue) + `onUpdateFreeLotteryTimeStampDict` | `_athlete_request()` (~line 1719) |

## Measured stream (offline build, existing account)

Sizes are encoded entity-message bytes. Build time is wall time on this PC since the previous method (includes argument building). The first call's time is the one-off `.def` parse that fills the method table.

| # | Method | Bytes | Need (evidence) |
|---|---|---|---|
| - | `resetEntities` + `createBasePlayer(Athlete)` | 4706 (8563 for a real account with items, `logs/server.log`) | Mandatory: creates the lobby player (LOBBY_FINDINGS "Working lobby route") |
| 1 | `onLogin` | 13 | Mandatory: login handshake of the Athlete |
| 2 | `onRoleCreateSuc` | 12 | Candidate: no recorded failure without it; not tested |
| 3-4 | `onSyncSwitches` / `onSetSwitches` (`URGENT_SWITCH_ENABLE_FORCE_UPGRADE`) | 44 + 43 | Candidate: not tested without |
| 5 | `syncServerTime` | 15 | Mandatory: client clock origin (LOBBY_FINDINGS "Server time", verified 2022-04-20) |
| 6 | `syncServerTimeZone` | 31 | Sent with 5; not tested alone |
| 7-9 | `onSetSwitches` x3 (`LOBBY_SWITCHES_OFF`) | 36 + 27 + 30 | Mandatory on a 2022 date: recall/sign-in popups otherwise block the lobby (code comment ~line 2338) |
| 10 | `onUpdateAlreadyShowSupplyID(saved id or 0)` | 12 | Weekly Supply push guard (see SUPPLY_RESTORATION.md) |
| 11 | `onUpdateDtsHallThemeID` | 12 | Mandatory: theme 0 breaks `leave_ui` (LOBBY_FINDINGS "Hall theme") |
| 12 | `onUpdateLuckyCarnivalData` | 465 | Mandatory: `UIMain.on_enter` aborted without it (LOBBY_FINDINGS "Breakthrough 2026-11-18") |
| 13 | `gmsyncRedPoints` | 12 | Likely needed: `showRedPoint` crash (LOBBY_FINDINGS line 24); not isolated |
| 14 | `onAccumulateChargeUpdate` | 43 | Candidate: no evidence either way |
| 15 | `onQueryAvailableSupplement({})` | 15 | Candidate: an empty stub. The full catalogue is sent on demand |
| 16 | `onUpdateBuySupplementCntDict({}, {}, {})` | 29 | Candidate: stub |
| 17 | `syncVipInfo` | 65 | Needed by draw-result and ad screens (LOBBY_FINDINGS "Diamonds") |
| 18 | `syncMonthPayRebateSpecialAwardInfo` | 155 | Candidate: no evidence either way |
| 19 | `onPersonalRecommendStateUpdated` | 27 | Needed by the Event panel (`personalRecommendCanBuy`) |
| 20-23 | `onSyncSwitches` / `onSetSwitches` for `SysEnableInGameAction`, `SysEnableEmoji` | 31 + 30 + 24 + 23 | Needed by the emote panel (LOBBY_FINDINGS "Open") |
| 24 | `syncDtsInGameActionAppearanceIDs` | 565 | Same as 20-23 |
| 25 | `syncDtsInGameActionSuitAppearanceIDs` | 320 | Same as 20-23 |
| 26 | `onUpdateDtsEmojiList` | 324 | Same as 20-23 |
| 27 | `enterHall` | 9 | Mandatory: starts the hall scene load |

Totals (script output):

```
resetEntities + createBasePlayer(Athlete)     4706 B   7 frag   163-290 ms (cold), ~160-210 ms (warm)
onLogin .. _lobby_data_calls()                2403 B   4 frag   ~190-330 ms (cold, .def parse), 3-6 ms (warm)
enterHall bundle                                 9 B   1 frag   <0.1 ms
TOTAL login stream                            7118 B  12 fragments
Athlete methods: 27 calls, 20 distinct; onSyncSwitches x3, onSetSwitches x6
```

`createBasePlayer` costs 160-290 ms on every login because `athlete_create_message()` builds a new `bwdefs.Defs()` and encodes 720 properties each time. That is server CPU, not client time.

## Where the startup time goes (saved logs)

From `bigworld_gateway/logs/server*.log` (`startup_trace.py --logs`): `Account.handshake` to the client's lobby-UI request burst (`requestEnterWorldOpenUI`) takes **38-61 s** (median per file). In the 2026-11-26 20:59 session (`logs/server.log` at that time): handshake 20:59:27, login bundle 20:59:28, first client burst 20:59:35, lobby UI burst 21:00:13. The gateway had sent everything within 1 s. The rest is the client loading `hall.scn` (LOBBY_FINDINGS: 35-40 s on LDPlayer with 4 cores, 41-54 s with 2 cores).

So the server stream (about 7 KB, under 1 s to build) is not the cause of the slow startup. Removing login messages cannot recover the 40 s scene load.

## Candidates for later work (all need a device test)

1. Cache the `bwdefs.Defs()` parse and the default Athlete stream between logins (saves 0.15-0.3 s server CPU per login). No client risk if the bytes stay identical.
2. Send the login bundle and `enterHall` as they are; do not drop rows marked "Mandatory".
3. Rows marked "Candidate" might be deferred, but each was added to stop a specific client error or has no record. Test one at a time.
4. The Supply catalogue (17,098 B, 25 fragments) is not part of the login stream; it goes out when the client sends `queryAvailableSupplement`.

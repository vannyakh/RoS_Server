# RO-107: Lobby START to battle handoff

## Objective

Restore the Athlete START chain documented in `bigworld_gateway/docs/LOBBY_FINDINGS.md` (Updates 3–4) so the gateway answers through `matchBattleGround` and schedules `_enter_battle`.

## Server changes

| Area | Change |
|------|--------|
| `bigworld_gateway/server/battle/session.py` | New `HallMatchSession` owns START → matching → ENTERING replies. |
| `bigworld_gateway/server/ros_server.py` | Delegates hall-team handlers; pins BF key at `matchBattleGround`; `_enter_battle` uses pinned key when `_last_bf` was cleared. |
| `bigworld_gateway/server/athlete_requests.py` | `HALL_START_SEQUENCE` constant for tests (names from `athlete_base_exposed.json` only). |

### Handler sequence (evidence: LOBBY_FINDINGS Update 3)

1. `getOpenMaintenanceFightTipFlag` → `onGetOpenMaintenanceFightTipFlag(False, 0)`
2. `createHallTeam(mode)` → `onEnterHallTeam` (solo, `HALL_TEAM_MAP_GROUP=1` / map 700)
3. `getReadyForBattleGround` → `syncReadyState` + `syncMatchState(1)` + `syncMatchingProgress`
4. `changeOccupation` / `reqPayedPartnerRel` → accepted (empty reply; client continues)
5. `matchBattleGround(1)` → `syncMatchState(2 ENTERING)` + delayed `_enter_battle`

### Regression fix

`matchBattleGround` now copies `_last_bf[addr]` into `_handoff_bf[addr]` before scheduling `_enter_battle`. Delayed entry no longer no-ops when no further Athlete packets arrive before `BATTLE_DELAY` (empty `_last_bf`).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/session -q --tb=line
```

Offline tests call `GateUDP._athlete_request` with decoded method names; no invented opcodes.

## LDPlayer / `to_match.sh` status (2026-11-26)

**BLOCKED on this workstation for live acceptance:** recent runs (`docs/TEST_REPORT.md`, `bigworld_gateway/docs/CREATE_ENTITY_FRAMING.md`) logged `athleteEnterHall` but **no** gateway lines for `createHallTeam`, `matchBattleGround`, or `-> battle: resetEntities`. That pattern means the client never sent START (lobby popups, tap coordinates, or slow `hall.scn`), not a missing handler.

When adb/LDPlayer is available, re-run:

```powershell
bigworld_gateway\tools\to_match.sh
```

Expect gateway log lines: `[BASEAPP] createHallTeam`, `[BASEAPP] matchBattleGround -> ENTERING`, `[BASEAPP] -> battle: resetEntities`.

Working reference: `config.cmd` (`SWITCH_TO=athlete`, `ATHLETE_CELL=off`, `GAME_DATE=2022-04-20`, `LOBBY_SWITCHES_OFF` without `SysEnableMonthSupply` on LDPlayer 2022 clock).

## Recommendation

- **QA:** run `tests/compatibility/gateway/session` on CI.
- **CTO:** mark RO-107 review-ready when pytest passes; live `VERIFIED` stays blocked until `to_match.sh` shows the handler log lines above.
- **RO-056:** unblocks once emulator START traffic is confirmed; server chain is covered by unit tests.
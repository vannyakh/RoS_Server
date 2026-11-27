# Test report (mobile restoration)

**Session:** 2026-11-26 · CTO restoration audit (updated RO-108)

## Commands run

```text
python scripts/validate_agent_registry.py
python scripts/validate_project_management.py
python -m tools.project_tracker.project_status
python -m tools.project_tracker.task_tracker --list
```

Result: registries OK (13 agents, 94 tasks at audit start). Original-client mobile re-test **not** executed in this audit pass.

## Mobile / LDPlayer

| Check | Result |
| --- | --- |
| Fresh login → hall | **VERIFIED** RO-108 — `to_match.sh` + `athleteEnterHall` in gateway log |
| START → map 700 | **VERIFIED** RO-108 — `createHallTeam` → `matchBattleGround -> ENTERING` → `-> battle: resetEntities` at 22:04:38–41 local (`docs/testing/hall_start_match.md`) |
| createEntity `space` trigger | **VERIFIED** (RO-056) — `BattleGroundSpace` 20001, `circleStage=1`; no RESEND on active match port after `space` |
| Workshop evolution | Separate track RO-095..RO-099; not mobile-verified |

## RO-108 / RO-056 (2026-11-26)

- RO-108: `bash bigworld_gateway/tools/to_match.sh` with `ADB=/e/LDPlayer/LDPlayer9/adb.exe` (~295 s); gateway session pytest **24 passed**.
- RO-056: Static createEntity framing in `bigworld_gateway/docs/CREATE_ENTITY_FRAMING.md`; live `space` + `entities_state` still **not** run this pass (match entry no longer the blocker).

## Verdict

Lobby START→battle mobile check: **1 VERIFIED** (RO-108). RO-056 criterion 3 (`trigger_battle` `space` + entity probe) is the next live step. Workshop continues in parallel (RO-096/097).

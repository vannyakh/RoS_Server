# Player system test report

**Date:** 2026-11-27  
**Scope:** Automated gateway unit tests + prior LDPlayer run (RO-113).

## Automated (this session)

```text
pytest tests/compatibility/gateway/player tests/compatibility/gateway/zone
     tests/compatibility/gateway/props tests/compatibility/gateway/bots
     tests/compatibility/gateway/jump  → 33 passed (after zone HP sync fix)
```

New: `tests/compatibility/gateway/player/test_player_entity.py` (battle loadout reset, elimination, bot factory).

## LDPlayer (RO-113) — not passing

| Step | Result |
| --- | --- |
| Solo Start → match | **FAIL** Network Error(15) |
| 9 bots / plane / parachute / land | **NOT_RUN** |

Evidence: [testing/solo_first_playable.md](testing/solo_first_playable.md).

**Ops checklist before retry:**

1. `powershell -ExecutionPolicy Bypass -File bigworld_gateway/client/scripts/setup_emulator.ps1`
2. Confirm `config.cmd` `ROS_PC_IP` matches LAN IP used in DNAT
3. Clear wrong emulator HTTP proxy (not gateway host)
4. `bash bigworld_gateway/tools/to_match.sh` with gateway log markers for `createHallTeam`, `matchBattleGround`, `resetEntities`

## Acceptance still open

Full human Solo match with mobile controls VERIFIED — blocked on RO-113, then combat/inventory waves RO-077+.

## Full 109-row checklist (QA → CTO)

Independent classification: [engineering/reviews/PLAYER_FUNCTION_CHECKLIST_QA.md](engineering/reviews/PLAYER_FUNCTION_CHECKLIST_QA.md)  
**0/109 VERIFIED** on LDPlayer; awaiting CTO task **RO-128** (proposed) assignment to `qa-engineer`.
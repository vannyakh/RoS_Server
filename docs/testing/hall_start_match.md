# RO-108: LDPlayer lobby START → battle acceptance

**Date:** 2026-11-26 (UTC+7)  
**Task:** RO-108 live proof after RO-107 server handoff fix  
**Status:** **VERIFIED** (gateway log lines present from scripted run)

## Preconditions

| Check | Result |
| --- | --- |
| ADB | `E:\LDPlayer\LDPlayer9\adb.exe` — device `emulator-5554` |
| Gateway | Already running (`bigworld_gateway/logs/server.log` active) |
| Reference flow | `docs/engineering/RO-107-hall-start-match.md`, `bigworld_gateway/docs/LOBBY_FINDINGS.md` Update 3–4 |

## Commands

### Device list

```powershell
& "E:\LDPlayer\LDPlayer9\adb.exe" devices
```

### Acceptance driver (Git Bash on Windows)

```powershell
& "C:\Program Files\Git\bin\bash.exe" -lc "export ADB=/e/LDPlayer/LDPlayer9/adb.exe && cd /c/Users/LUFY/Desktop/RoS_Server/bigworld_gateway && bash tools/to_match.sh"
```

Duration: **~295 s** (script waits for hall load, popup taps, START tap, then battle handoff).

### Offline regression (RO-107)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/session -q --tb=line
```

### Log markers (before → after RO-108 run)

| Marker | Before | After |
| --- | ---: | ---: |
| `athleteEnterHall` (HTTP keypoint) | 2 | 5 |
| `createHallTeam mode=` | 2 | 3 |
| `matchBattleGround -> ENTERING` | 2 | 3 |
| `-> battle: resetEntities` | 2 | 3 |

The RO-108 run incremented each START-related marker by **1** (third full lobby → match cycle in this log).

## RO-108 log excerpts (`logs/server.log`, local time)

**START chain** — `[22:04:38]`:

```text
      [BASEAPP] <- Athlete.getOpenMaintenanceFightTipFlag args=
      [BASEAPP] <- Athlete.createHallTeam args=04000000
      [BASEAPP] createHallTeam mode=4 -> onEnterHallTeam (solo, leader 9879120763)
      [BASEAPP] <- Athlete.getReadyForBattleGround args=
      [BASEAPP] getReadyForBattleGround -> ready + MATCHING
      [BASEAPP] <- Athlete.matchBattleGround args=01
      [BASEAPP] matchBattleGround -> ENTERING
```

**Battle handoff** — `[22:04:41]` (~3 s after ENTERING, `BATTLE_DELAY`):

```text
      [BASEAPP] -> battle: resetEntities + BattleGroundAvatar (map 700, char 20001)
```

`to_match.sh` tail output (`logs/ro108_to_match.log`):

```text
      [BASEAPP] -> battle: resetEntities + BattleGroundAvatar (map 700, char 20001)
```

## Acceptance

- Client **did** send START: `createHallTeam` → `getReadyForBattleGround` → `matchBattleGround`.
- Gateway **did** answer ENTERING and schedule `_enter_battle` (`resetEntities` + `BattleGroundAvatar` on map 700).
- Evidence source: `bigworld_gateway/logs/server.log` (not pytest alone).

## Notes

- An older UDP session (`51892`) showed `[BASEAPP RESEND]` during the new match (`56690`); the new session ACKed battle entity fragments normally. Unrelated to START handoff.
- **RO-056:** Match entry is unblocked for live `trigger_battle.txt` / `space` work; not executed in this task (gateway code unchanged).
- Earlier 2026-11-26 sessions without these log lines were **BLOCKED** (client never sent START — popups/taps/hall load). This run used the documented `to_match.sh` tap sequence.

## Verdict

**VERIFIED** — RO-107 handoff is live-accepted on LDPlayer with log proof for the full START → battle chain.
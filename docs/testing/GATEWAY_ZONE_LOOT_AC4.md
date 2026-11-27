# RO-064 / RO-066: Zone and loot LDPlayer AC4

**Date:** 2026-11-27 (UTC+7)  
**Tasks:** RO-064 (shrinking safe zone), RO-066 (DtsProp spawn and pickup)  
**AC4 verdict:** **BLOCKED** (no live session; do not mark pass without `bigworld_gateway/logs/server.log` proof)  
**Original-server compatible:** **not claimed** (gateway params in `bigworld_gateway/server/battle/data/zone.json` and `loot.json` only)

## Scope

| Layer | What it proves | Status (this run) |
| --- | --- | --- |
| Unit | `tests/compatibility/gateway/zone`, `tests/compatibility/gateway/props` | **PASS** (8 tests) |
| AC4 LDPlayer | Minimap circles, shrink, poison, ground loot, pickup, backpack | **BLOCKED** |

AC4 depends on a full lobby → match handoff. If Start fails, zone and props markers never appear — see `docs/testing/hall_start_match.md` and `docs/testing/solo_first_playable.md` (RO-113 **Network Error(15)**).

---

## Preconditions

| Check | Operator action | Pass criterion |
| --- | --- | --- |
| LDPlayer | Emulator running, landscape 1920×1080 | `adb devices` shows one device |
| ADB | Set `ADB` to your `adb.exe` (see `bigworld_gateway/tools/to_match.sh`) | Device list succeeds |
| APK | `com.netease.chiji` patched per `bigworld_gateway/client/` docs | Game reaches hall, not stuck on Verify |
| DNS / proxy | `bigworld_gateway/client/scripts/setup_emulator.ps1` after IP change | `athleteEnterHall` appears in log after login |
| Single gateway | One `ros_server.py` / `dns_server.py` pair | No duplicate Python stacks |
| Env | `BATTLE_SPACE=off` (space still created via MatchSession; avoids duplicate auto-space) | `logs/ro113_env.txt` or echo in parent shell before `start.cmd` |
| Data | `bigworld_gateway/server/battle/data/zone.json`, `loot.json` present | Module start lines show non-zero stages / entries |

---

## Commands

### 1. Stop and restart gateway

From `bigworld_gateway/`:

```powershell
.\stop.cmd
cmd /c "call config.cmd && set BATTLE_SPACE=off && echo BATTLE_SPACE=%BATTLE_SPACE% > logs\ac4_env.txt && start.cmd"
```

Logs: `bigworld_gateway/logs/server.log`, `dns.log`, `*_err.log`.  
Optional tail:

```powershell
Get-Content bigworld_gateway\logs\server.log -Wait -Tail 40
```

### 2. Emulator DNS (after LAN / IP change)

```powershell
powershell -ExecutionPolicy Bypass -File bigworld_gateway\client\scripts\setup_emulator.ps1
```

### 3. ADB device check

```powershell
& "E:\LDPlayer\LDPlayer9\adb.exe" devices
```

(Adjust path; export the same path in Git Bash as `ADB`.)

### 4. Drive lobby → map 700

Git Bash on Windows (from repo root):

```powershell
& "C:\Program Files\Git\bin\bash.exe" -lc "export ADB=/e/LDPlayer/LDPlayer9/adb.exe && cd bigworld_gateway && bash tools/to_match.sh"
```

Expect `-> battle: resetEntities` in the log tail (~3–5 min). Stay in match through **play** phase (post countdown) so zone stages and loot spawns run.

### 5. Unit regression (no emulator)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/zone tests/compatibility/gateway/props -q --tb=line
```

**This run:** `8 passed in 2.30s` (2026-11-27).

---

## Log grep patterns (`bigworld_gateway/logs/server.log`)

Source lines: `bigworld_gateway/server/battle/modules/zone.py`, `props.py`.

### Git Bash (from `bigworld_gateway/`)

```bash
grep -c '\[BATTLE\] zone module started' logs/server.log
grep '\[BATTLE\] zone stage' logs/server.log
grep '\[BATTLE\] props module started' logs/server.log
grep '\[BATTLE\] props spawn' logs/server.log
grep '\[BATTLE\] props pickup' logs/server.log
```

Optional poison / failure:

```bash
grep '\[BATTLE\] zone poison fatal' logs/server.log
grep '\[BATTLE\] props reject pickup' logs/server.log
```

### PowerShell

```powershell
Select-String -Path bigworld_gateway\logs\server.log -Pattern '\[BATTLE\] zone stage'
Select-String -Path bigworld_gateway\logs\server.log -Pattern '\[BATTLE\] props spawn'
Select-String -Path bigworld_gateway\logs\server.log -Pattern '\[BATTLE\] props pickup'
```

### Marker table (fill after AC4 run)

| Pattern | Meaning | Count (pre-run) | Count (post-run) |
| --- | --- | ---: | ---: |
| `-> battle: resetEntities` | Match entered | — | |
| `[BATTLE] zone module started` | Zone module registered | 0 | |
| `[BATTLE] zone stage` | Stage shrink + circle props | 0 | |
| `[BATTLE] props module started` | Loot module registered | 0 | |
| `[BATTLE] props spawn` | DtsProp createEntity sent | 0 | |
| `[BATTLE] props pickup` | Successful tryPickUp | 0 | |
| `[BATTLE] zone poison fatal` | HP reached 0 in poison (optional) | 0 | |

**Pre-run note (2026-11-27):** Current `server.log` contains **no** `[BATTLE] zone` or `[BATTLE] props` lines — AC4 not executed on device in this agent session. `adb` was not on PATH; use full path above.

Example expected lines (format only):

```text
      [BATTLE] zone module started (N stages)
      [BATTLE] zone stage 1 circle=(...) blue_r=... rest=...s dps=...
      [BATTLE] props module started (M entries)
      [BATTLE] props spawn eid=... propID=... at (x,y,z)
      [BATTLE] props pickup eid=... propID=... (Gun|...)
```

---

## AC4 pass/fail checklist

Record **PASS** only when both **client observation** and **matching log lines** exist in the same session. **FAIL** if logs contradict the UI. **NOT_RUN** if match entry failed. **BLOCKED** if emulator or gateway ops cannot be completed.

### RO-064 — safe zone

| # | Check | Client (LDPlayer) | Log | Result |
| --- | --- | --- | --- | --- |
| Z1 | Match entered | Map 700 loaded, HUD active | `-> battle: resetEntities` | |
| Z2 | Circles on minimap | White and blue circles visible | ≥1 `[BATTLE] zone stage` after play phase | |
| Z3 | Shrink over time | Blue (safe) circle radius decreases between stages | Multiple `zone stage` lines with decreasing `blue_r=` | |
| Z4 | Rest countdown | Rest-time UI updates between stages | `updateCircleRestTime` / `onRequestCircleRestTime` traffic (optional); stage line shows `rest=Ns` | |
| Z5 | Poison damage | HP drops outside blue circle | `isInPoisonArea` updates; optional `zone poison fatal` if death tested | |

### RO-066 — loot and pickup

| # | Check | Client (LDPlayer) | Log | Result |
| --- | --- | --- | --- | --- |
| L1 | Ground props | Items visible near spawn / `loot.json` coords | ≥1 `[BATTLE] props spawn` | |
| L2 | Pickup button | Tap pickup; item in backpack; prop gone | `[BATTLE] props pickup eid=...` | |
| L3 | Double pickup | Second tap on same prop fails | No second pickup line; may see `props reject pickup missing` | |
| L4 | Out of range | Pickup refused when far | `props reject pickup out of range` if tested | |

### Session gates (blockers)

| Gate | Result (2026-11-27 agent) | If FAIL, fix before Z/L checks |
| --- | --- | --- |
| ADB reachable | **BLOCKED** (not on PATH in agent shell) | Install PATH or use full `adb.exe` in `ADB=` |
| Lobby START → battle | **UNKNOWN** (not re-run here) | RO-108 harness; RO-113 network/DNS |
| Zone/props log markers | **FAIL** (0 matches in current log) | Complete match + play phase on device |

---

## Operator steps when BLOCKED

1. Confirm `config.cmd` `ROS_PC_IP` matches the PC LAN IP the emulator can reach.
2. Run `setup_emulator.ps1`; confirm DNAT to gateway DNS (see RO-113 notes in `docs/testing/solo_first_playable.md`).
3. Clear wrong emulator HTTP proxy if present (RO-113: `192.168.100.137:8080` vs gateway LAN).
4. `stop.cmd` → single `start.cmd` with `BATTLE_SPACE=off`.
5. `to_match.sh` with correct `ADB=`; wait for `resetEntities`, then **wait through countdown** into play.
6. Walk to a loot row from `loot.json` (or use positions logged in `props spawn`); tap pickup.
7. For poison (Z5): stand outside blue circle after a stage shrink; watch HP and logs.
8. Attach: screenshot(s), filled marker table, and 10–30 lines of grep output for zone stage + props spawn/pickup.

Do **not** set task AC4 to PASS from pytest alone.

---

## Unit evidence (not AC4)

| Command | Result (2026-11-27) |
| --- | --- |
| `pytest tests/compatibility/gateway/zone -q --tb=line` | 4 passed (per task registry) |
| `pytest tests/compatibility/gateway/zone tests/compatibility/gateway/props -q --tb=line` | **8 passed in 2.30s** |

Rules exercised in tests: staged circles and poison in `zone.py`; spawn, range, and duplicate pickup in `props.py`. Values are gateway data, not `app/game/rules.py` or original RoS tables.

---

## Verdict

| Task | Unit AC | AC4 LDPlayer |
| --- | --- | --- |
| RO-064 | **PASS** (pytest) | **BLOCKED** — no device run; zero zone markers in log |
| RO-066 | **PASS** (pytest) | **BLOCKED** — no device run; zero props markers in log |

**Recommendation:** Keep RO-064 and RO-066 in **testing** until an operator completes this checklist with PASS rows and log excerpts. Reuse RO-108/`to_match.sh` once Start is unblocked (RO-113 network path).
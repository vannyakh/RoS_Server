# RO-113: First-playable Solo BR LDPlayer acceptance

**Date:** 2026-11-26 (UTC+7)  
**Task:** RO-113  
**Verdict:** **FAIL / BROKEN** (live run did not reach Solo Start → match)  
**Original-server compatible:** **not claimed** (gateway private path only)

## Preconditions (this run)

| Check | Result |
| --- | --- |
| ADB | `E:\LDPlayer\LDPlayer9\adb.exe` — device `emulator-5554` |
| APK | `com.netease.chiji` installed (also `com.ros.client` present) |
| Gateway | Restarted via `bigworld_gateway/start.cmd` with `BATTLE_SPACE=off` written to `bigworld_gateway/logs/ro113_env.txt` |
| DNS redirect | Re-ran `bigworld_gateway/client/scripts/setup_emulator.ps1` (DNAT udp/53 → `192.168.180.137:53`) after first Network Error |
| Driver | `bash tools/to_match.sh` (same harness as RO-108) |

## Commands

```powershell
cmd /c "call config.cmd && set BATTLE_SPACE=off && echo BATTLE_SPACE=%BATTLE_SPACE% > logs\ro113_env.txt && start.cmd"
powershell -ExecutionPolicy Bypass -File bigworld_gateway\client\scripts\setup_emulator.ps1
& "C:\Program Files\Git\bin\bash.exe" -lc "export ADB=/e/LDPlayer/LDPlayer9/adb.exe && cd /c/Users/LUFY/Desktop/RoS_Server/bigworld_gateway && bash tools/to_match.sh"
```

Artifact dir (screenshots + harness notes): `tests/compatibility/gateway/solo_first_playable/artifacts/`

## Log marker counts (post-run `bigworld_gateway/logs/server.log`)

| Marker | Count |
| --- | ---: |
| `athleteEnterHall` | 0 |
| `createHallTeam` | 0 |
| `matchBattleGround` | 0 |
| `-> battle: resetEntities` | 0 |
| space / plane / Robot / aliveNum / jump markers | 0 |

No START chain and no MatchSession battle markers were written in this session log.

## Acceptance checklist

| Gate | Result | Evidence | Owning task (on fail / not run) |
| --- | --- | --- | --- |
| Solo Start (lobby START → battle handoff) | **FAIL** | Screenshot `tests/compatibility/gateway/solo_first_playable/artifacts/during_to_match_sm.jpg` — client dialog **Network Error(15)** during load (0%). No `createHallTeam` / `matchBattleGround` / `-> battle: resetEntities` lines in `bigworld_gateway/logs/server.log`. | **RO-107 / RO-108** (handoff never reached; live Start blocked by emulator↔gateway network path) |
| 9 bots visible | **NOT_RUN** | Blocked by Start FAIL; no Robot / solo_fill / aliveNum log lines. | **RO-069** (spawn/visibility); fill config **RO-110** |
| Aircraft / plane | **NOT_RUN** | Blocked by Start FAIL; no plane module / `inJumpArea` markers. | **RO-062** |
| Parachute | **NOT_RUN** | Blocked by Start FAIL; no `requestGetOffPlane` / parachute markers. | **RO-063** |
| Land | **NOT_RUN** | Blocked by Start FAIL; no land / forcedPosition evidence. | **RO-063** |

## Environment notes (ops, not opcodes)

1. First capture: Network Error(15) while verifying/loading — `during_to_match.png` / `during_to_match_sm.jpg`.
2. Emulator DNS props were `192.168.180.23` / `8.8.8.8` while `config.cmd` uses `ROS_PC_IP=192.168.180.137`. `setup_emulator.ps1` reapplied DNAT; retry `to_match.sh` still produced **0** hall/battle markers.
3. Connectivity dump showed `HttpProxy: [192.168.100.137] 8080` (wrong LAN vs gateway). Global `http_proxy` settings read as null; proxy may be injected by the emulator network stack.
4. **2026-11-27:** `setup_emulator.ps1` now clears `http_proxy` before device runs. Re-run setup, then RO-113.
4. After `am start`, UI stayed on package **Verifying...** (e.g. `after_clear_proxy_sm.jpg` at 71%) and never reached lobby START.
5. Nested `ros_server.py` / `dns_server.py` processes (venv + system Python re-exec) observed; `BATTLE_SPACE=off` was set for the start.cmd parent env (`logs/ro113_env.txt`).

## Unit / schema check

Optional pytest under `tests/compatibility/gateway/solo_first_playable/` asserts this checklist file exists and contains the five gates with Result + Owning task columns. It does **not** invent Mercury opcodes or claim original-server behavior.

## Verdict

**BROKEN** for first-playable LDPlayer acceptance: Start failed with Network Error(15); downstream gates NOT_RUN. No VERIFIED. No original-compatible claim.

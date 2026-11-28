# Agent sprint — Phases B → C → D

> **Function checklist work:** one agent per lane in [CHECKLIST_TASKS.md](CHECKLIST_TASKS.md), following
> [`.claude/skills/ros-function-check/SKILL.md`](../.claude/skills/ros-function-check/SKILL.md). Take the LDPlayer
> lock (`tools/ldplayer_lock.ps1`) before driving the emulator or restarting the gateway.

**Active:** [PHASE_STATUS.md](PHASE_STATUS.md) · [SERVER_GAMEPLAY_ROADMAP.md](SERVER_GAMEPLAY_ROADMAP.md)

| Phase | Sprint goal | Acceptance script |
|-------|-------------|-------------------|
| **A** | Lobby (maintenance) | Manual hall2 + no traceback |
| **B** | START → map 700 handoff | `tools/cycles/phase_b_handoff.ps1` |
| **C** | Drop → zone death → **H1** result UI → lobby | `ld_debug_match.ps1 -RequireLobby -ZoneTest` |
| **D** | Loot spawn + equip in match | TBD after C green |

**Charter:** [AGENTS.md](AGENTS.md) · **Matrix:** [gameplay_function_matrix.json](gameplay_function_matrix.json)

---

## Phase B (matchmaking) — run now

**Prerequisite:** `stop.cmd` → `start.cmd` (clears RESEND storms).

```powershell
cd c:\Users\Lufy\Desktop\Server
.\sync_server_list.ps1
cd ros_server_v2
.\tools\cycles\phase_b_handoff.ps1
```

Pass: `server.log` shows `enterHall` → `matchBattleGround` → `_enter_battle` / `createBasePlayer`; `logs/phase_b_match.png` is in-match HUD.

| Role | Task |
|------|------|
| Device | Run `phase_b_handoff.ps1`; on fail, capture `ld_debug_script.txt` |
| Harness | One fix only if handoff fails (e.g. `BATTLE_DELAY`, team member theme id) |
| RE | Map ids for `BATTLE_MAP` env (700 vs Fiord) — read-only |

**Matrix rows:** `match_start`, `queue`, `ready_countdown`, `room_assignment` (document synthetic space 1).

---

## Phase C (core BR) — after B passes

**Code:** H1 `die_call()` already in `battle_flow.finish()` (iter 16).

```powershell
.\tools\cycles\ld_debug_match.ps1 -TapPlay -RequireLobby -TapStart -LobbyWaitSeconds 300 -WaitMatchSeconds 300 -ZoneTest
```

Pass: `killed by the zone` + `match result` in server.log; result/death UI.

| Role | Task |
|------|------|
| Harness | H2 only if H1 fails live: `CM_DELTAS` for `onBattleGroundDie`, or `GS_END` on space |
| Device | No START until `wait_server_log.ps1` sees `enterHall` |

**Matrix rows:** `elimination`, `placement`, `return_to_lobby`, `safe_zone`, `flight_route`.

---

## Phase D (extended BR) — gated on C

First slice (roadmap):

1. `dtsBattlegroundPropAppearanceList` on `avatar_create_messages` (outfit in match — partial §20).
2. Map 700 loot table / building spawns (replace manual `loot` triggers).
3. Verify gun pickup → `equip_weapon` on LDPlayer.

No work until Phase C acceptance is green.

---

## Shared environment

1. **One IP:** `config.cmd` `ROS_PC_IP` = DNS DNAT = server list (`adb_common` reads config).
2. **Clock:** `date -u 042012002022.00` on emulator.
3. **No Frida** at launch (DCTOOL crash).
4. Log iterations in `harness/iteration_log.jsonl`.

## Cursor Task spawn

```
Device:  "RoS Phase B handoff"
Harness: "RoS Phase C H1 verify"
RE:      "RoS map id table" (composer-2.5-fast)
```
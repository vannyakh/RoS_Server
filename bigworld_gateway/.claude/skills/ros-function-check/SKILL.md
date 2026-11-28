---
name: ros-function-check
description: Check and fix Rules of Survival game functions from docs/RESTORATION_CHECKLIST.md on the ros_server_v2 gateway. Use when asked to verify, test, fix or restore checklist items (e.g. "check 19.06", "work on lane 3", "fix the shop items"), or to pick up a lane from docs/CHECKLIST_TASKS.md. Covers the LDPlayer lock, evidence rules, and how to update the checklist.
---

# Check and fix checklist functions

The checklist is `docs/RESTORATION_CHECKLIST.md`: 518 items, one line each, `— STATUS (note)`.
Lanes (which agent owns which sections and files) are in `docs/CHECKLIST_TASKS.md`.
Hard rules are in `docs/AGENTS.md`. Rule 1 matters most: never inject client Python to skip server work.
A function only counts when the gateway makes it work.

## 1. Pick work

1. Read your lane in `docs/CHECKLIST_TASKS.md`. If the user named items, use those. If they named none,
   take your lane's items in this order: `CODED` → `NOT TESTED` → `PARTIAL` → `FAIL`.
2. Take a batch of 3–6 items that one test run can cover (e.g. all of the 22.x Depot views in one lobby visit).
3. Read the relevant LOBBY_FINDINGS section and code before testing. `FUNCTION_INVENTORY.md` maps
   functions to code.

## 2. Use LDPlayer safely

- Take the lock first: `.\tools\ldplayer_lock.ps1 acquire -Owner <lane> -Task "<ids>"`. If it says busy, do not
  touch the emulator or restart the gateway. Write code or wait.
- Other agents (Claude Code sessions, Cursor, Antigravity) and the user may share the device. Before a run, check
  for other `adb`/`frida`/`ros_server.py` processes started recently. Tell the user before you restart the
  game, because they may be playing on it.
- `touch` the lock every ~10 minutes in long runs; `release` when done, even on failure.
- Screen is 1600x900. PLAY (790,655), START (1280,805), notice popup close (1536,90).
  `tools/cycles/ld_debug_match.ps1` handles the popup and takes the lock itself.
- After login a notice popup can cover PLAY. The lobby scene takes 40–70 s to load. A RESEND burst while the lobby
  loads is normal if the log then shows `Remote ACKed`. A RESEND storm that never stops means a corrupt session:
  `stop.cmd`, `start.cmd` (only while you hold the lock).
- Never start frida-server before the game is at its menu (DCTOOL crash). Never attach probes while the lobby
  is loading.
- Gateway log: `logs/server.log`. Client log: `adb -s emulator-5554 logcat -d -v time`.
  Screenshot: `adb exec-out screencap -p > file` (use `cmd /c` in PowerShell, not `>` on binary).

## 3. Evidence rules

| Mark | When |
|---|---|
| `PASS` | You saw it work on screen this run, plus the matching gateway log line. Not from reading code. |
| `FAIL` | Not implemented, or you saw it break. Say how in the note. |
| `PARTIAL` | Works with fixed, empty or solo-only data. Say what is missing. |
| `CODED` | You wrote or found code for it and have not seen it work. |
| `CLIENT` | Client-side only. Becomes `PASS` once seen working in game. |
| `NOT TESTED` | No evidence. |

Save screenshots as `logs/checklist/<id>.png` (e.g. `logs/checklist/19.06.png`). Put the key log line or
screenshot name in the note: `— PASS (2026-11-26 LDPlayer; logs/checklist/19.06.png)`. Phone results go in
the note too. Every PASS so far is LDPlayer only.

## 4. Fix

- One hypothesis per run. Change only your lane's files. Put new logic in your own module and add only a
  short hook in shared files (`battle_flow.py`, `ros_server.py`).
- Base the protocol on evidence: entity defs (`server/extract/entities_out/`, `bwdefs.py`), client bytecode
  read with read-only Frida payloads (`client/frida/payloads/`), or the original server's documented behavior.
  Don't guess wire formats. Record what you learned in `docs/LOBBY_FINDINGS.md`.
- Restart the gateway to load server changes (with the lock held), then retest the item.

## 5. Record

1. Edit the item's line in `docs/RESTORATION_CHECKLIST.md`: checkbox `[x]` only for PASS, status, short note.
2. Run `python tools/checklist_counts.py` (rewrites the totals; fails on a checkbox/status mismatch).
3. If the item maps to a row in `docs/FUNCTION_INVENTORY.md`, update its mark there too.
4. If you found a blocker for another lane, add it to that lane's "Requests:" line in `docs/CHECKLIST_TASKS.md`.
5. Release the lock. Report the ids you changed, old → new status, and what is still unverified.

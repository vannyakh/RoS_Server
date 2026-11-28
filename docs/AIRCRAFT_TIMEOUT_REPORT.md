# Solo preparation island, aircraft and result screen: timeout report

Status: **in progress.** The code fixes are made and the gateway suite passes. Only one of the five
required device runs has finished, and LDPlayer crashed during it.

- Date: 2026-11-28
- Branch: `sync/rosgg-b967a5a` (changes not committed yet)

Evidence folders are git-ignored and stay on the test machine:

- `bigworld_gateway/logs/checklist/measure_1937/`
- `bigworld_gateway/logs/checklist/runs/run1/`
- `bigworld_gateway/logs/checklist/runs/user_match_1940/`
- `bigworld_gateway/logs/result_gold_keys.txt`

## Root causes

### 1. Lobby hang after login (`_realEnterHall` AttributeError on `None.GetComponent`)

**Cause.** The gateway sent `enterHall` 0.2 s after the large lobby bundle. The client was still
processing that bundle and stalled for about 12 s on the emulator. `enterHall` then ran before the
lobby UI existed.

**Fix.** `enterHall` now waits until the client has ACKed every packet of the lobby bundle. It is
sent anyway after `HALL_ACK_MAX` (20 s).

- Switch: `HALL_WAIT_ACK=on` (default).
- Device: `enterHall sent (lobby bundle ACKed)`; the lobby loaded with no new error.

### 2. Match started while the client was still on the loading screen

**Measurement** (`measure_1937`, screenshots with log times):

- The loading screen stayed until 19:38:46. The world was visible at 19:38:56.
- `onRecvClientFrameLevel`, `getOnTrain`, `onRecvClientFPS`, `skydive2MoveDir` and `onTryingToRun`
  all arrive *during* loading.
- `verifyClientValue`, `reqFallFollowCurrentInfo`, `switchOperateMode`, `onDtsSelectStart`,
  `jumpEnd` and `onGetFallDamage` arrive at 19:38:49–53, once the world is up.
- The client sent no position report at all in this window.

**Fix.** The default is now `MATCH_START_ON=inworld,position`. The match starts on the first request
from the in-world set. The set can be replaced with `MATCH_START_REQUESTS`.

- `MATCH_START_ON=avatar` keeps the old behaviour (start on any request from the player's own avatar).
- `MATCH_START_TIMEOUT` (120 s) still starts a match that never reports.
- Run 1 started with `match start: client in world: verifyClientValue`.

### 3. Result screen showed placeholder text and stayed over the lobby

The client's code was read with the read-only Frida payload
`bigworld_gateway/client/frida/payloads/result_gold_keys.py`. It shows the call chain:

- `iBattleGround.onBattleGroundResult(gameType, teamSize, rank, total, bannerID, results, killerInfo)`
  → `_delayShowResult` → `UIBattlegroundsResultGold`.
- `showResult` reads `results[player.gid]`, then `getGPs` (5 values), `randomGP` and `exp`.
- For each member it reads `nickname`, `kill` and `getGPs[0..1]`.

Four separate causes:

| Cause | Effect seen | Fix |
| --- | --- | --- |
| The args were map 700, mode, placement, kills, 0, `{reason, victory}`, `{}` | `FailedUnpickle`; the panel kept "LINGZI 玲" ×5, "/120 Teams" | Sends the client's layout: rank, alive-at-start, and the row keyed by gid (`results.py`, `battle_flow.result_call`) |
| The row had `gps` but no `getGPs` / `randomGP` | KeyError in `showResult` | The row carries the Gold-screen keys |
| `onBattleGroundDie` was sent on a Solo death | Squad spectate panel: "Your team still have a chance!", Spectate | Only sent with `RESULT_DIE_CALL=on` |
| The gateway returned to the lobby 3 s after the result | Panel left over the lobby | The lobby return now waits for Exit/Next (`requestLeaveDynamicSpace`); fallback `RESULTS_LOBBY_DELAY` is 60 s |
| `EnableEntertainScore` switch on | Exit/Next → KeyError `newEntertainScore` | Switched off at login (`LOBBY_SWITCHES_OFF`) |

On device, the results stage was reached in run 1, but the emulator was down by then. **The fixed
result screen has not been seen on device yet.**

### 5. Result went to the wrong client method

**Cause.** The client index of `onBattleGroundResult` is raw .def index + 2, not + 3. Index 267 ran raw
265, `onBattleGroundGoldBattleResult`.

**Evidence (run 2):**
- The traceback goes through `_showGoldArenaResult`.
- The Gold-battle casual-points panel opened.
- The args were read with the wrong layout, giving `FailedUnpickle` x32.

**Fix.** `CM_DELTAS` +2 for `onBattleGroundResult` and `onBattleGroundDie` (`battle_flow.py`).

**Result (run 3).** No `FailedUnpickle`. The result panel still did not appear (open blocker 2).

### 4. Gateway resent to a dead client forever

**Cause.** LDPlayer crashed in run 1 at about 02:02. The keepalive kept resending every unacked
packet every 0.5 s: 40 764 resends in about an hour, until the emulator came back. Nothing ever
timed the channel out.

**Fix.** `PEER_TIMEOUT` (default 60 s). After that many seconds with no packet from the client, the
keepalive stops, the unacked packets are dropped, and the match is ended once as an abandon. A new
login starts a fresh channel.

- Code: `ros_server._drop_dead_peer`.
- Tests: `test_stale_channel.py`.

## Changed files

- `bigworld_gateway/server/ros_server.py`:
  - ACK-gated `enterHall`;
  - `EnableEntertainScore` off;
  - `PEER_TIMEOUT` dead-client drop.
- `bigworld_gateway/server/battle/session.py`: the in-world match-start set.
- `bigworld_gateway/server/battle/modules/results.py`:
  - the client result layout;
  - no Solo die call;
  - the lobby return waits for Exit.
- `bigworld_gateway/server/battle/flow.py`: the results stage limit is 60 s.
- `bigworld_gateway/server/battle_flow.py`: the result row keys.
- `bigworld_gateway/client/frida/payloads/result_gold_keys.py`: the read-only probe (new).
- Tests:
  - `tests/compatibility/gateway/session/test_enter_hall_after_ack.py` (new);
  - `test_match_flow.py`;
  - `test_stale_channel.py`;
  - `results/test_results_module.py`;
  - `supply/test_supply_login_stream.py`.

## Test results

- `pytest tests/compatibility/gateway`: **1630 passed, 1 xfailed** (2026-11-28, after all of the
  changes above).

Device runs (Solo, 1 human + 9 bots, `ZONE_TIME_SCALE=0.1`):

| Run | Login / lobby | waiting | aircraft | parachute | ground | results | lobby | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ok (ACK-gated enterHall) | 0 s → 30 s | 8 s, forced jump | 304 s (timed fallback) | 188 s | reached (victory), `record_match ok` | not reached | LDPlayer crashed at about 02:02; HUD showed "10 LEFT" |
| 2 | ok (Events popup covered PLAY on the first try) | 30 s | 8 s, forced | 304 s: 4 759 position reports, all at y 19300 (the client hovered) | 188 s | casual-points panel, client log `FailedUnpickle` | after 60 s | Wrong method index: see cause 5 |
| 3 | ok | 30 s | 8 s, forced | 46.5 s, landed from the client's position | 188 s | `onBattleGroundResult` ran with no error; the battle HUD stayed and the frame did not change for 60 s; no result panel | after 60 s | Victory: the player survived the last circle |
| 4 | invalid | | | | | | | Started from the lobby after a match: START opened the Supply shop; the client stayed on "Matched!" (`MapLoader.doLoadMap` 'NoneType'.get) and never entered the map |
| 5 | not run | | | | | | | |

## Open blockers

1. **Sometimes the client hovers after a forced jump.**
   - Run 2: every position report stayed at y 19300 for 5 minutes. Run 3: the same forced jump fell
     and landed in 46 s.
   - Not explained yet. The scripted Jump tap in run 4 is not evidence, because that run never
     entered the map.
   - The older notes below describe run 1.

   **Landing takes 300 s (run 1).**
   - What run 1 shows: after the forced jump at (-9421, 19300, -3705), the server log has no
     further position report. The fall phase never advanced, and the player was still free-falling
     at 02:01:46.
   - Landing came only from `JUMP_LAND_MAX` (300 s).
   - Next device check: whether the client reports positions during a fall started by the button
     instead of `force`.
2. **No result panel after `onBattleGroundResult` (run 3).**
   - The client ran it with no error and logged the result-screen sounds and the SDK `af_first_game`
     event.
   - The battle HUD stayed and the screen did not change until the lobby return. The return was the
     60 s fallback; Exit/Next was never seen.
   - Probe: `client/frida/payloads/result_state.py` (read-only). Run 4 ran it too late, during the
     lobby load. Next: probe 3–5 s after the result.
3. **Second match in one session (run 4).** Pressing START from the lobby after a match never loads
   the map.
4. **Emulator stability.**
   - The emulator's load average was 18 right after the reboot.
   - The crash may be load; it is not proven to be the game.
5. **Remaining in-battle client errors** (per-frame AttributeErrors): `PlayerAthlete.hp`,
   `checkHoldBreath`, `_checkWeaponValue`, `MoveUnit.character`, `AIM_KEYS`,
   `getSpeedExtraFactor`. See `runs/user_match_1940/ERRORS.md`.
6. **Device runs.** Run 3 is the only clean full match so far.

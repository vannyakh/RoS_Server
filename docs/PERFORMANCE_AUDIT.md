# Performance audit: startup, Supply, Supreme black screen

Task RO-106, from the evidence of RO-101 to RO-104 (2026-11-26). Detail: [STARTUP_FLOW.md](STARTUP_FLOW.md), [SUPPLY_RESTORATION.md](SUPPLY_RESTORATION.md), [RESOURCE_LOADING.md](RESOURCE_LOADING.md), [PERFORMANCE_BENCHMARK.md](PERFORMANCE_BENCHMARK.md).

Status values: NOT_CHECKED, INVESTIGATING, FIXED, VERIFIED, BLOCKED. Nothing is VERIFIED without a device run.

## Findings

| # | Issue | Origin | Evidence | Status |
|---|---|---|---|---|
| 1 | Slow startup | Client (hall.scn load on LDPlayer) | The gateway sends the full 7 KB login stream within 1 s of the handshake. The lobby UI appears 38-61 s later (saved logs). | INVESTIGATING |
| 2 | Server CPU per login | Server | `createBasePlayer` re-parses `.def` files and re-encodes 720 properties: 160-350 ms per login | FIXED (RO-105): `.def` parse and default stream cached; warm build 0.7 ms, bytes identical |
| 3 | Full Supply catalogue sent at login | — | Not the case. Login sends an empty `onQueryAvailableSupplement({})` stub; the full 17 KB catalogue is sent only on `queryAvailableSupplement`. Test `test_supply_login_stream.py`. | Not a defect |
| 4 | Supply opens by itself at login (weekly push) | Server | The client calls `setHasAlreadyShowSupplyID` with no arguments (`.def`), but `ros_server.py` reads an INT32. The call fails, nothing is saved, and the next login sends id 0 again. Two strict xfail tests. | FIXED (RO-105); device check pending: stored id 9778 vs 9779 |
| 5 | Supply opens by itself at login (monthly push) | Server | `hasAlreadyShowMonthSupply` (in `childClientPropertyList2`) is always sent as 0. The client sends `setHasAlreadyShowMonthSupply` and then queries Supply about 3 s after the lobby appears. The gateway now saves it (`supply_month_push`), but the `.def` has no reply method, and the login value is still the default. Probe the value on the device before changing `childClientPropertyList2`. | INVESTIGATING |
| 6 | Supreme Supply black content | Client device clock | `supplement_utils.getCurrentMonthSupplementID` uses `time.time()`; the last monthly box ends 2022-12-30. `config.cmd` keeps `SysEnableMonthSupply` on. | BLOCKED on the device date or a client change |
| 7 | Supply open latency on the server | Server | Building the reply takes about 0.13-0.19 ms. `supply_cache` cuts it to about 0.0004 ms; wired in RO-105, warm reply 0.023 ms. | FIXED |
| 8 | Draw validation gaps | Server | Unknown box id, a currency the box does not accept, and a free draw after a refusal all still give a prize. Four strict xfail tests. | FIXED (RO-105); real draws need a device check |
| 9 | FPS, frame time, memory, GPU | Client / emulator | No device data | BLOCKED (RO-104, no adb) |
| 10 | Star Supply | — | Nothing in the extracts or logs identifies it | NOT_CHECKED |

## What the server cannot fix

Hall scene load time, GPU and shader cost, texture decoding, and the device-clock check in the monthly Supreme page all run in the original APK. A faster Python gateway does not change them.

## Next work

- **RO-105** (backend-architect; waits on the RO-097 review because RO-097 holds `ros_server.py`):
  - make the `setHasAlreadyShowSupplyID` handler take no argument;
  - keep `SysEnableMonthSupply` off unless the operator says the device date is 2022;
  - cache the `.def` parse and the default property stream, keeping the bytes identical;
  - wire in `supply_cache` and `perf_monitor`;
  - reject unknown boxes and currencies a box does not accept.
- **RO-104**: owner starts LDPlayer and sets `ADB`, then capture logcat, gfxinfo and meminfo while opening Supply 20 times.

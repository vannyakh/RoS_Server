# Performance benchmark (gateway, offline)

Task RO-106. Every number here came from a command run on 2026-11-26 on the developer PC (Python 3.12.10). These are in-process timings with `perf_counter`: no network, no database, no device. They are not client FPS or end-to-end latency.

## Commands

```powershell
.\.venv\Scripts\python.exe bigworld_gateway/tools/startup_trace.py
.\.venv\Scripts\python.exe bigworld_gateway/tools/bench_gateway.py
```

Raw JSON: `reports/performance/gateway_supply_bench.json`.

## Login stream (startup_trace.py, one cold run)

| Segment | Bytes | Fragments | Build time |
|---|---|---|---|
| resetEntities + createBasePlayer(Athlete) | 4706 | 7 | 354 ms cold (RO-101 saw 160-290 ms warm) |
| onLogin .. _lobby_data_calls() | 2403 | 4 | 251 ms cold, 3-6 ms warm |
| enterHall | 9 | 1 | — |
| **Total** | **7118** | 12 | 605 ms cold |

The cold time is mostly the one-off `.def` parse and the per-login re-encoding of 720 Athlete properties. In saved logs (RO-101), the gateway finished sending the login stream within 1 s of the handshake. The lobby UI appeared 38-61 s later, because the client was loading `hall.scn`.

## Supply catalogue reply (bench_gateway.py, 200 iterations)

| Row | p50 ms | p95 ms | mean ms | Bytes |
|---|---|---|---|---|
| supplement_reply.uncached (current code) | 0.125-0.151 | 0.147-0.403 | 0.132-0.189 | 17090 |
| supplement_reply.cached (supply_cache, not wired) | 0.0003-0.0004 | 0.0005-0.0006 | 0.0003-0.0006 | 17090 |

These are the ranges over two runs. The cached bytes match the current reply byte for byte. The cache saves about 0.15 ms each time Supply opens, which is too small to explain any lag the user can see.

Draw timing (264 boxes × 200 iterations): 1x draws take about 0.002 ms and 10x draws about 0.007 ms, with or without the cache.

## After RO-105 (startup_trace.py)

| Segment | Before | After |
|---|---|---|
| TOTAL login stream bytes | 7118 B | 7118 B (identical) |
| Warm createBasePlayer | ~207 ms | 0.5-0.7 ms |
| Cold createBasePlayer | 220-354 ms | 209-280 ms (one-off `.def` parse) |
| queryAvailableSupplement warm | 0.205 ms | 0.023 ms |

## Not measured

FPS, frame time, CPU/GPU, memory, end-to-end Supply open time on the device, and multi-player load. RO-104 is BLOCKED: this host has no adb.

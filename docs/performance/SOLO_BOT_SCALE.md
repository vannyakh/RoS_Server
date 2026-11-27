# Solo bot scale gates (RO-112)

Gateway-local **offline** measurement for static Robot (type 58) bot spawns via
`bigworld_gateway/server/battle/modules/bots.py`. Uses `MatchSession` enqueue only —
no live Mercury socket, no LLM bots, **no original RoS capacity claim**.

## Scope

| Item | Detail |
| --- | --- |
| Measured gate | **N = 9** (first-playable default from RO-110 / solo_fill) |
| Later targets | 29, 59, 119 — listed as **NOT measured** until a disposable run exists |
| FastAPI / Locust | Out of scope; see `docs/performance/PERFORMANCE_BASELINE.md` |

## N = 9 measured run

- Measured at: `2026-11-27T00:51:44+0700`
- Iterations: **50** spawn+teardown cycles (warmup **5**)
- Spawn enqueue: mean **86.7339 ms**, p50 **83.4141 ms**, p95 **119.0723 ms**
- Teardown (leaveAoI): mean **0.019 ms**, p95 **0.0293 ms**
- Wire per cycle: **10** packets, **751** bytes total
- Process RSS delta during bench: **2.78 MB** (start **49.49 MB** → end **52.27 MB**)
- CPU sample (pytest process): **0.0%**

Two users for 10 seconds in Locust is unrelated. `MAX_PLAYERS_PER_MATCH` is not used here.

## Scale targets (NOT measured)

- **N = 29** — status: **NOT measured**. Single offline probe only; no iterative gate run.
- **N = 59** — status: **NOT measured**. Single offline probe only; no iterative gate run.
- **N = 119** — status: **NOT measured**. Single offline probe only; no iterative gate run.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests/performance/test_solo_bot_scale.py -q
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/bots -q
```

Report: `reports/performance/solo_bot_scale.json`.

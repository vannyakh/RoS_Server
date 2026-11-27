"""Offline benchmark of the gateway Supply reply build and draws (no server, no database).

Run from the repo root:

    .venv/Scripts/python.exe bigworld_gateway/tools/bench_gateway.py [--iterations 200]

Compares building the queryAvailableSupplement argument uncached (py(supplement_info()), as
ros_server.py does today) with supply_cache.supplement_info_blob(), and times draw(sid, 1) and
draw(sid, multi_count(sid)) over every box id that has a prize pool. Prints a table and writes
reports/performance/gateway_supply_bench.json.
"""
import argparse
import json
import os
import platform
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER = os.path.join(ROOT, "bigworld_gateway", "server")
sys.path.insert(0, SERVER)

import athlete_requests as reqs  # noqa: E402
import perf_monitor  # noqa: E402
import supply_cache  # noqa: E402

OUT = os.path.join(ROOT, "reports", "performance", "gateway_supply_bench.json")


def run(mon, name, fn, iterations):
    for _ in range(iterations):
        with mon.measure(name) as m:
            out = fn()
            m.bytes = len(out) if isinstance(out, (bytes, bytearray)) else 0
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iterations", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    n = args.iterations
    mon = perf_monitor.Monitor(maxlen=max(n * 64, 1024))

    # First (cold) calls, which include reading the JSON extracts.
    t0 = time.perf_counter()
    info = reqs.supplement_info()
    cold_load_ms = (time.perf_counter() - t0) * 1000.0
    supply_cache.invalidate()
    t0 = time.perf_counter()
    cached = supply_cache.supplement_info_blob()
    cold_cache_ms = (time.perf_counter() - t0) * 1000.0
    uncached = reqs.py(info)
    if cached != uncached:
        print("FAIL: cached blob differs from py(supplement_info())")
        return 1

    run(mon, "supplement_reply.uncached", lambda: reqs.py(reqs.supplement_info()), n)
    run(mon, "supplement_reply.cached", supply_cache.supplement_info_blob, n)

    sids = sorted(s for s in info if reqs.supplement_prizes(s))
    rng = random.Random(args.seed)
    for sid in sids:
        multi = reqs.multi_count(sid)
        for _ in range(n):
            with mon.measure("draw.single.uncached"):
                reqs.draw(sid, 1, rng)
            with mon.measure("draw.single.cached"):
                supply_cache.draw(sid, 1, rng)
            with mon.measure("draw.multi.uncached"):
                reqs.draw(sid, multi, rng)
            with mon.measure("draw.multi.cached"):
                supply_cache.draw(sid, multi, rng)

    summary = mon.summary()
    rows = ["supplement_reply.uncached", "supplement_reply.cached", "draw.single.uncached",
            "draw.single.cached", "draw.multi.uncached", "draw.multi.cached"]
    print("iterations=%d boxes_with_pool=%d supplement_bytes=%d python=%s"
          % (n, len(sids), len(cached), platform.python_version()))
    print("%-28s %8s %10s %10s %10s %10s %10s" % ("name", "count", "p50_ms", "p95_ms", "mean_ms",
                                                   "max_ms", "mean_B"))
    for name in rows:
        s = summary[name]
        print("%-28s %8d %10.4f %10.4f %10.4f %10.4f %10.0f" % (
            name, s["count"], s["p50_ms"], s["p95_ms"], s["mean_ms"], s["max_ms"],
            s["mean_bytes"]))
    u, c = summary["supplement_reply.uncached"], summary["supplement_reply.cached"]
    speedup = u["mean_ms"] / c["mean_ms"] if c["mean_ms"] else None
    if speedup:
        print("supplement reply mean speedup: %.0fx" % speedup)

    report = {
        "benchmark": "gateway_supply",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": "python bigworld_gateway/tools/bench_gateway.py --iterations %d" % n,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "iterations": n,
        "draw_iterations_per_box": n,
        "boxes_with_pool": len(sids),
        "supplement_blob_bytes": len(cached),
        "cached_equals_uncached": True,
        "cold": {"supplement_info_load_ms": cold_load_ms,
                 "supplement_blob_first_build_ms": cold_cache_ms},
        "results": {name: summary[name] for name in rows},
        "supplement_reply_mean_speedup": speedup,
        "notes": "Offline in-process timing (time.perf_counter); no network, no database. "
                 "draw rows count one sample per box per iteration.",
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print("wrote %s" % os.path.relpath(args.out, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

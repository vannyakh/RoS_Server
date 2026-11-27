"""RO-119 benchmark: legacy load_accounts/save_account vs local_store.

Run from the repository root:

    .venv/Scripts/python.exe tests/compatibility/gateway/local_store/bench_local_store.py

Works on generated files in a temp directory. The real saved_accounts.json is
only measured with os.path.getsize; it is never opened. Writes
reports/performance/gateway_local_store_bench.json.
"""

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "bigworld_gateway" / "server"))
sys.path.insert(0, str(HERE))

import legacy_store  # noqa: E402
import local_store  # noqa: E402

REAL_FILE = ROOT / "bigworld_gateway" / "server" / "saved_accounts.json"
REPORT = ROOT / "reports" / "performance" / "gateway_local_store_bench.json"


def _account(i):
    return {
        "name": f"player{i:04d}",
        "char_type": 20001 + i % 6,
        "inventory": {"items": [{"itemID": 1000 + j, "number": j + 1} for j in range(8)],
                      "gold": i * 13, "diamond": i * 7},
        "signin": {"level": i % 30, "day": "2026-11-26"},
        "appearance": {"gender": i % 2, "body": {"0": [1, 2, 3], "1": [4, 5, 6]}},
        "portrait": f"file-{i:06d}",
    }


def make_file(path, keys):
    data = {"default": _account(0)}
    for i in range(1, keys):
        data[f"inventory:{100000 + i}"] = _account(i)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def stats(samples_s):
    ms = sorted(s * 1000 for s in samples_s)
    return {
        "count": len(ms),
        "p50_ms": statistics.median(ms),
        "p95_ms": ms[min(len(ms) - 1, int(round(0.95 * (len(ms) - 1))))],
        "mean_ms": statistics.fmean(ms),
        "max_ms": ms[-1],
    }


def timed(fn, n):
    out = []
    for i in range(n):
        t0 = time.perf_counter()
        fn(i)
        out.append(time.perf_counter() - t0)
    return out


def run_case(workdir, keys, loads, saves):
    old = os.path.join(workdir, f"old_{keys}.json")
    new = os.path.join(workdir, f"new_{keys}.json")
    make_file(old, keys)
    make_file(new, keys)
    size = os.path.getsize(old)
    local_store._stores.clear()
    local_store.load(new)  # warm the cache once, as a running gateway would be

    res = {
        "file_bytes": size,
        "keys": keys,
        "load.legacy": stats(timed(lambda i: legacy_store.load_accounts(old), loads)),
        "load.local_store": stats(timed(lambda i: local_store.load(new), loads)),
        "get_one_key.legacy": stats(timed(lambda i: legacy_store.load_accounts(old).get("default"), loads)),
        "get_one_key.local_store": stats(timed(lambda i: local_store.get(new, "default"), loads)),
        "save.legacy": stats(timed(lambda i: legacy_store.save_account(old, "default", {"n": i}), saves)),
        "save.local_store": stats(timed(lambda i: local_store.save(new, "default", {"n": i}), saves)),
    }
    with open(old, "rb") as a, open(new, "rb") as b:
        res["files_identical_after_run"] = a.read() == b.read()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loads", type=int, default=1000)
    ap.add_argument("--saves", type=int, default=200)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    real_size = os.path.getsize(REAL_FILE) if REAL_FILE.exists() else None
    with tempfile.TemporaryDirectory() as tmp:
        cases = {"200_keys": run_case(tmp, 200, args.loads, args.saves)}
        if real_size:
            # Smallest generated file at least as large as the real one.
            k = 1
            while True:
                probe = os.path.join(tmp, "probe.json")
                make_file(probe, k)
                if os.path.getsize(probe) >= real_size:
                    break
                k += 1
            cases["real_size"] = run_case(tmp, k, args.loads, args.saves)

    report = {
        "benchmark": "gateway_local_store",
        "task": "RO-119",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": "python tests/compatibility/gateway/local_store/bench_local_store.py"
                   f" --loads {args.loads} --saves {args.saves}",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "notes": [
            "Single thread, generated files in a temp directory; real saved_accounts.json size "
            "measured with os.path.getsize only.",
            "local_store loads are warm-cache (stat + deep copy); legacy loads open and parse each call.",
            "local_store saves include flush + fsync + os.replace; legacy saves rewrite in place without fsync.",
        ],
        "real_saved_accounts_bytes": real_size,
        "loads": args.loads,
        "saves": args.saves,
        "cases": cases,
    }
    text = json.dumps(report, indent=2)
    if not args.no_write:
        REPORT.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

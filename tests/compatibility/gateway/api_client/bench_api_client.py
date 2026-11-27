"""RO-120 benchmark: urllib-per-request (a copy of account_link._call) vs ApiClient keep-alive.

Run from the repository root:
  .venv/Scripts/python.exe tests/compatibility/gateway/api_client/bench_api_client.py [--iterations 500]
Writes reports/performance/gateway_api_client_bench.json.
"""

import argparse
import json
import platform
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / "bigworld_gateway" / "server"), str(HERE)]

from api_client import ApiClient  # noqa: E402
from fake_api import FakeApi  # noqa: E402

KEY = "bench-key-not-a-secret"
REPORT = ROOT / "reports" / "performance" / "gateway_api_client_bench.json"


def urllib_call(base, method, path, body, timeout=2.0):
    """account_link._call as of RO-120, minus the settings lookup."""
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json", "X-Gateway-Key": KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return {"_error": e.code}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def measure(fn, method, iterations):
    body = {"price": 100, "props": [1001, 1002]} if method == "POST" else None
    for _ in range(20):  # warm-up
        fn(method, "/api/v1/gateway/bench", body)
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = fn(method, "/api/v1/gateway/bench", body)
        samples.append((time.perf_counter() - start) * 1000)
        assert result and result.get("method") == method, result
    samples.sort()
    return {
        "p50_ms": round(statistics.median(samples), 4),
        "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 4),
        "mean_ms": round(statistics.fmean(samples), 4),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=500)
    args = parser.parse_args()
    api = FakeApi()
    client = ApiClient(api.url, KEY, timeout=2.0)
    results = {}
    try:
        for method in ("GET", "POST"):
            before = api.connections
            old = measure(lambda m, p, b: urllib_call(api.url, m, p, b), method, args.iterations)
            old["server_connections"] = api.connections - before
            before = api.connections
            new = measure(client.call, method, args.iterations)
            new["server_connections"] = api.connections - before
            results[method] = {"urllib_per_request": old, "api_client": new,
                               "p50_speedup": round(old["p50_ms"] / new["p50_ms"], 2)}
    finally:
        client.close()
        api.stop()
    report = {
        "benchmark": "gateway_api_client",
        "task": "RO-120",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": "python tests/compatibility/gateway/api_client/bench_api_client.py "
                   f"--iterations {args.iterations}",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "server": "local http.server.ThreadingHTTPServer, HTTP/1.1, 127.0.0.1 (no app work per request)",
        "iterations_per_case": args.iterations,
        "warmup_per_case": 20,
        "results": results,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"wrote {REPORT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()

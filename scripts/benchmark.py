"""Measure /health latency against a running local server."""

import sys
from time import perf_counter

import httpx


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    samples = []
    try:
        with httpx.Client(timeout=2.0) as client:
            for _ in range(30):
                started = perf_counter()
                response = client.get(f"{base}/health")
                response.raise_for_status()
                samples.append((perf_counter() - started) * 1000)
    except httpx.HTTPError as exc:
        raise SystemExit(f"Health check failed: {exc}") from exc
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    print(f"samples={len(samples)} p50={samples[len(samples)//2]:.2f}ms p95={p95:.2f}ms")


if __name__ == "__main__":
    main()

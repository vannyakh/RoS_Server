# Performance baseline

Measured by `tests/performance/test_load.py` on 2026-11-10. Locust 2.47 ran the profile in `tools/load_generator/locustfile.py` against a temporary Uvicorn process. The database was a temporary SQLite file, not `ros_server.db`.

The current aggregated Locust row in `reports/performance/measured.json` is the passing rerun. An earlier run logged 4 HTTP requests and then a WebSocket timeout. That earlier row is not the current file.

| Measurement | Value |
| --- | --- |
| Simulated players | 2 |
| Requested duration | 10 seconds |
| Requests | 77 |
| Failures | 0 |
| Requests per second reported by Locust | 8.54 |
| Average latency | 12.1 ms |
| p50 | 2 ms |
| p95 | 120 ms |
| p99 | 170 ms |
| Server process RSS, including child processes | 95.1 MB |
| CPU sample | 0.0% over the sampler's short window |

The profile includes register, login, profile, lobby, match list, and WebSocket auth. Two users for 10 seconds is not a capacity result. `MAX_PLAYERS_PER_MATCH` is 100 in settings and was not used as a capacity result.

Database pool size, queue depth, and a multi-minute soak were not measured in this run.

# Performance baseline

Measured by `tests/performance/test_load.py` on 2026-11-10. Locust 2.47 ran the profile in `tools/load_generator/locustfile.py` against a temporary Uvicorn process. The database was a temporary SQLite file, not `ros_server.db`.

The aggregated Locust row in `reports/performance/measured.json` was:

| Measurement | Value |
| --- | --- |
| Simulated players | 2 |
| Requested duration | 10 seconds |
| Requests | 4 |
| Failures | 0 |
| Requests per second reported by Locust | 13.39 |
| Average latency | 145.5 ms |
| p50 | 180 ms |
| p95 | 180 ms |
| p99 | 180 ms |
| Server process RSS, including child processes | 85.8 MB |
| CPU sample | 0.0% over 0.2 seconds |

Four requests at the reported rate fit a short active window, not a full 10 second task loop. The profile also defines profile, lobby, match-list, and WebSocket auth tasks. This run's aggregate row does not show a sustained rate for those tasks. `MAX_PLAYERS_PER_MATCH` is 100 in settings and was not used as a capacity result.

Database pool size, queue depth, and a multi-minute soak were not measured in this run.

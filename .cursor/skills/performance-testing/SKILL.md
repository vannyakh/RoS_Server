---
name: performance-testing
description: Runs the Locust player profile and records latency percentiles. Use when measuring login, lobby, match list, or WebSocket auth load.
---

# Performance testing

## Workflow

1. Start Uvicorn with `DATABASE_URL` pointed at a temporary SQLite file.
2. Run `locust -f tools/load_generator/locustfile.py --headless`.
3. Read the aggregated row from the CSV: requests, failures, average, 50%, 95%, 99%.
4. Write the numbers to `reports/performance/measured.json`.
5. Say that the user count is not `MAX_PLAYERS_PER_MATCH`.

## Output

The measured JSON file.

## Failure

A non-zero Locust exit code or any failure count leaves the task unapproved.

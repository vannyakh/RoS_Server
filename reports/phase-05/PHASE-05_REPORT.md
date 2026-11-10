# Phase 05 — Performance and deployment

Checkpoint: CP-0007 / PHASE-05-PERFORMANCE-DEPLOYMENT

HEAD remains `6b7c55cc6a1659169292ce123a8105814b2d13df`. This phase was not committed and was not pushed. Compose was not started.

## Load sample

`python -m pytest tests/performance/test_load.py -q --tb=line` returned **1 passed in 14.28s**.

`reports/performance/measured.json` now has 77 requests, 0 failures, about 8.54 requests per second, average latency 12.1 ms, p95 120 ms, and server RSS 95.1 MB. Two simulated players for 10 seconds is not a capacity result.

The full suite in the same session returned **82 passed, 1 skipped**.

## Storage and backup

Alembic head remains `93510e8bf194`. The live SQLite file was not copied. `docs/operations/RELEASE_STATUS.md` says to stop the server before copying `ros_server.db`, to keep the copy out of git, and not to delete `legacy_players` or downgrade the live file.

## Release

This tree is not a release. Docker Desktop returned HTTP 500 from its engine API. PostgreSQL was not executed. RO-009 is still ready, so RO-011 and RO-034 stay blocked.

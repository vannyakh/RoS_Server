---
name: observability
description: Records function execution, Prometheus metrics, traces, and Sentry-compatible errors. Use when adding logs or dashboards for API, database, or tick paths.
---

# Observability

## Workflow

1. Wrap the operation in `function_tracker.track` and mark the lifecycle stage.
2. Use `hot=True` for the game tick. The default hot sample rate is 0, so ticks are not logged one by one.
3. Increment `ros_*` metrics with bounded labels only.
4. Confirm `/metrics` renders and does not contain `player_id`.
5. Leave `SENTRY_DSN` empty in tests. `capture_exception` still stores a local event.

## Output

A redacted JSON record and the metric names that were scraped.

## Failure

If a label value comes from a user id, remove it before merging.

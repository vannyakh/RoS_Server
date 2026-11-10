# Function tracking

`tools.function_tracker` writes one JSON log line per recorded execution. The record contains `function_id`, `feature`, `function_name`, `execution_id`, `request_id`, `session_id`, `player_id`, `match_id`, `started_at`, `completed_at`, `duration_ms`, `status`, `error_code`, `error_message`, and `trace_id`.

Stages, in order of use:

`REQUEST_RECEIVED`, `VALIDATION`, `AUTHORIZATION`, `SERVICE_EXECUTION`, `DATABASE_OPERATION`, `GAME_STATE_UPDATE`, `RESPONSE_SENT`.

HTTP requests record the non-tick stages. `PersistenceService.save_player_progress` records `DATABASE_OPERATION`. The game tick uses `hot=True`. The default hot sample rate is 0, so tick executions are not logged individually. Tick duration still updates `ros_game_tick_duration_seconds`.

Bearer tokens and `password=` text are replaced with `[redacted]`. `tests/unit/test_function_tracker.py` covers that redaction and the hot-path drop.

OpenTelemetry spans are kept in process memory. Sentry events are stored locally and are sent only when `SENTRY_DSN` is set. No DSN was set for the tests.

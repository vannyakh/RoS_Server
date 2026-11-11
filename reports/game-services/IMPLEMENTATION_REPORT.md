# Game services implementation report

Recorded: 2026-11-11
Branch: `main`
HEAD: `7affe25`
No commit and no push.

## Architecture implemented

One FastAPI process. Routers stay thin. Lobby, player, match, and account rules stay in the existing services. Files were not moved into a new package tree.

The Android client should use `docs/API_CONTRACT.md`. WebSocket and live `/matches` use the account id. Durable lobbies and match records use the player id from `GET /api/v1/players/me`.

## Routes added or changed

Added:

- `PATCH /api/v1/players/me`
- `GET /api/v1/lobby/{lobby_id}`
- `GET /api/v1/lobby/{lobby_id}/members`

Changed behavior on existing routes:

- Join reserves capacity with `current_players < max_players` in the same transaction as the membership insert. A missing lobby is 404.
- The last member to leave sets the lobby to `closed`.
- Joining a stored match fails with 409 when that player already has another `scheduled`, `lobby`, or `running` match.
- A WebSocket session lookup that fails unexpectedly is reported as an invalid token. The log line contains the exception type only.

Logout, ready, leave, inventory, match records, and `/ready` were already present and were kept.

## Database

No model change and no new Alembic revision. Head remains `93510e8bf194`.

SQLite connections now set a 5 second busy timeout so concurrent joins wait for the writer. PostgreSQL options were not changed.

`ros_server.db` was not opened, migrated, or deleted.

## Services

- Player: nickname and avatar update. Level, experience, username, and statistics are not writable.
- Lobby: member read, atomic capacity, empty lobby close. No leader role, because the tables have no leader column.
- Match records: one active stored match per player. Finalize still stores the `rewards` object and does not pay experience, currency, or items.
- Matchmaking: left as the in-memory WebSocket queue. Duplicate queue entry returns success `Already queued`. A player already in a live match is rejected. No Redis queue was added.
- Realtime: existing single-socket policy is now covered by a test. A second socket closes the first with code 4000.

## Tests

Command:

```text
python -m pytest -q --tb=line
```

Result: **89 passed, 1 skipped, 6 warnings in 76.43s**.

The skip is `tests/database/test_postgres.py::test_postgres_account_roundtrip`: `POSTGRES_TEST_URL is not set, so PostgreSQL was not executed`. The JSONB dialect check in that file passed. This is not a PostgreSQL integration pass.

No existing test was deleted, xfailed, or skipped to get this result. There are no failing tests in this run.

Warnings: Starlette's deprecation notice for httpx, and Python 3.12's sqlite3 datetime adapter warning inside the legacy-player migration test.

WebSocket tests that passed in this run:

- valid auth and invalid token
- two clients, disconnect, and reconnect
- revoked token rejected
- second connection replaces the first with close code 4000
- the Locust profile, including `websocket_auth`

The load profile wrote `reports/performance/measured.json`: 2 users for 10 seconds, 76 requests, 0 failures, average 12.1 ms, p50 2 ms, p95 110 ms, p99 160 ms, server RSS 95.4 MB. That sample is not match capacity. The older baseline timeout, 4 HTTP requests and a WebSocket timeout, was not reproduced.

No separate lint, format, or type-check command is configured in `requirements.txt`. None was run.

## Security

- Passwords stay on the `pwdlib` recommended hasher.
- Only the SHA-256 session hash is stored. Logout revokes that row.
- Expired JWTs, missing session rows, revoked rows, and expired session rows return 401.
- A missing bearer header returns 401.
- Profile updates cannot change level or the account username.
- Logs for a failed WebSocket lookup do not include the token or the hash.
- Reward amounts sent by a client are not applied.

Still true, and unchanged on purpose:

- `GET /api/v1/items`, `GET /api/v1/lobby`, `GET /api/v1/matches`, and `GET /metrics` do not require a session.
- A player can add catalog items and currency to their own inventory through the inventory routes.
- The login failure limit is per process, not shared.

## Limits

- Live queue and live matches are in memory. Run one worker. Do not run multiple Uvicorn workers against that state.
- A player can be a member of more than one durable lobby.
- There is no leader. Empty means the last member left, and the lobby closes.
- The one-active-match rule is a transaction check, not a partial unique index.
- Equipment slots are not implemented.
- Stored match rewards are not paid. In-memory match end still updates kills, wins, and matches played.
- PostgreSQL production readiness is not claimed.

## Outstanding

- Run `tests/database/test_postgres.py` against a disposable database when `POSTGRES_TEST_URL` is set.
- Decide whether a leader column is wanted before adding one.
- Write an explicit local reward rule before paying experience or currency.
- Add equipment only after a slot model exists.
- RO-009 is still `ready` in the CTO registry. This session did not change task status.
- Point the Android client at this contract, starting with register, login, profile, and a two-player durable lobby.

## Files created

- `docs/API_CONTRACT.md`
- `docs/SERVICE_ARCHITECTURE.md`
- `reports/game-services/PHASE_01_AUDIT.md`
- `reports/game-services/IMPLEMENTATION_REPORT.md`
- `tests/integration/test_game_services.py`

## Files modified

- `app/api/v1/lobby.py`
- `app/api/v1/players.py`
- `app/infrastructure/database.py`
- `app/networking/websocket.py`
- `app/repositories/lobby_repository.py`
- `app/repositories/match_repository.py`
- `app/schemas/player.py`
- `app/services/lobby_service.py`
- `app/services/match_service.py`
- `app/services/player_service.py`
- `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md`
- `testdata/reference/compatibility_matrix.json`
- `tests/integration/test_auth_session.py`
- `tests/integration/test_websocket_reliability.py`

`reports/performance/measured.json` was rewritten by the load test. Compatibility counts are 43 unknown, 0 compatible. Matrix test evidence was updated for session checks, nickname update, lobby leave, lobby capacity, and the absent experience and currency payouts.

These paths were already dirty and were not edited here: `.cursor/management/discoveries.json`, `docs/reverse-engineering/CLIENT_ANALYSIS.md`, `docs/reverse-engineering/RESEARCH_INDEX.md`, `docs/reverse-engineering/UNKNOWN_BEHAVIOR.md`.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m pytest -q --tb=line
```

Use one process. Live matches are in memory. `--reload` is fine for development. Do not add extra workers.

## Next milestone

Connect the Android API client to register, login, `GET` and `PATCH /api/v1/players/me`, and a two-player durable lobby: create, join, ready, leave. Keep the in-memory WebSocket queue for the playable match, and do not treat that queue as the durable room. Leave equipment and match payouts until a written local rule exists.

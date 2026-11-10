# Test inventory

QA read `tests/` and the handlers those tests call. The full pytest suite was not run in this pass. Pass, fail, and skip counts are **Unknown**.

This inventory describes tests of this server. It is not evidence of original Rules of Survival compatibility. `tests/compatibility/test_matrix.py` requires every matrix row to stay `compatibility_status` `unknown`.

## Task report

TASK ID: project-audit tests inventory
AGENT: qa-engineer
PHASE: testing
STATUS: report only; no task was set to completed

IMPLEMENTATION: none; read-only inventory
FILES CREATED: reports/project-audit/tests.md
FILES MODIFIED: none
DISCOVERIES: see findings below
DATABASE CHANGES: none
API CHANGES: none
GAME FUNCTION CHANGES: none
TESTS EXECUTED: none. The CTO is running the suite. QA did not invoke pytest.
TEST RESULTS: **Unknown**. No assertions were executed, so there is no failing-assertion list from this pass.
COMPATIBILITY EVIDENCE: none. Local tests are not original-server proof.
KNOWN ISSUES: logout, durable lobby leave, health database readiness, suspended accounts, and session-row assertions have no covering tests.
RECOMMENDATION: keep this as a QA report. The CTO decides status.

OBJECTIVE: inventory `tests/` and name missing coverage for the five areas above.
IMPLEMENTATION SUMMARY: 31 test modules plus `tests/conftest.py`. 66 `test_` functions were counted from source. No test function is parametrized.
SECURITY CONSIDERATIONS: response schemas omit `password_hash` and `token_hash` in `tests/security/test_responses.py`. No test asserts a stored session row, revocation, or a suspended account.
DEPENDENCIES: PostgreSQL execution depends on `POSTGRES_TEST_URL`. Whether that variable is set for the CTO run is **Unknown**.

## How the suite is wired

**Confirmed fact.** `tests/conftest.py` sets `DATABASE_URL` to `sqlite+aiosqlite:///./test_ros.db` before the app is imported. `db_session` drops and recreates tables on that engine. `client` drives the ASGI app and clears the in-memory login-failure map. `reset_engine` clears in-memory match state.

**Confirmed fact.** `tests/database/test_postgres.py` compiles a PostgreSQL `JSONB` statement with no live server. `test_postgres_account_roundtrip` skips when `POSTGRES_TEST_URL` is unset. A skip is not a PostgreSQL pass. This pass did not observe a skip or a run.

## Area inventory

| Area | Files | What the tests cover |
| --- | --- | --- |
| Fixtures | `tests/conftest.py` | Disposable SQLite, HTTP client, engine reset |
| Integration auth | `tests/integration/test_auth.py` | Register, duplicate username 409, case-insensitive login, bearer profile, generic 401, short password 422, `GET /health` status 200, empty live lobby and match lists |
| Integration match | `tests/integration/test_match.py` | Saved kills, wins, and matches on the profile; missing match 404; in-memory queue visible on `GET /api/v1/lobby` or `/matches` |
| Integration WebSocket | `tests/integration/test_websocket.py` | Register, login, `auth`, `player.input`, `lobby.join` ack |
| Integration lobby HTTP | `tests/integration/test_lobby_routes.py` | Item catalog paging, unauthenticated lobby create 401, open lobby, duplicate code 409, join member, create team, join team, second team seat 409 |
| Unit protocol | `tests/unit/test_protocol.py` | Version 1, input range, increasing sequence, `lobby.join` parse, unknown action, rate limit |
| Unit gameplay | `tests/unit/test_gameplay.py` | Bot fill, movement, elimination and win record, pickup and heal, zone damage, in-memory `leave_queue` |
| Unit engine | `tests/unit/test_engine.py` | One tick applies input with no database |
| Unit observability | `tests/unit/test_observability.py` | `/health` 200 and request id; `/metrics` names, including `ros_database_query_duration_seconds`; no `player_id` label; Sentry-compatible event type |
| Unit function tracker | `tests/unit/test_function_tracker.py` | Stage log, secret redaction, hot-path sampling drops tick records |
| Unit Redis | `tests/unit/test_redis_cache.py` | Injected client round trip; connection errors return empty results |
| Compatibility matrix | `tests/compatibility/test_matrix.py` | Audit is empty and every feature stays `unknown` with an unauthorized-reference prefix |
| Compatibility auth | `tests/compatibility/authentication/test_login.py` | Player simulator register, login, profile; expired JWT 401; malformed JSON message |
| Compatibility player | `tests/compatibility/player/test_profile.py` | Nickname, level 1, zero matches, no `password_hash` |
| Compatibility lobby | `tests/compatibility/lobby/test_lobby_rules.py` | In-memory simulator capacity, team, and ready flag |
| Compatibility matchmaking | `tests/compatibility/matchmaking/test_queue.py` | Two in-memory players reach countdown |
| Compatibility gameplay | `tests/compatibility/gameplay/test_scenario.py` | Seeded scenario matches `testdata/expected_results/solo_elimination.json` twice |
| Compatibility inventory | `tests/compatibility/inventory/test_pickup.py` | Nearby loot enters the in-memory inventory |
| Compatibility weapons | `tests/compatibility/weapons/test_shot.py` | Local pistol damage of 22 on this server's rules |
| Compatibility results | `tests/compatibility/match_results/test_results.py` | Placement, kills, win flag, and stat totals from the scenario runner |
| Models | `tests/models/test_constraints.py` | Unique username, player foreign key, currency overdraft message, unique match participant |
| Repositories | `tests/repositories/test_account_repository.py` | Normalized username lookup and hashed password; durable lobby rejects a second membership and a full room; match result stored and illegal transition rejected |
| Relationships | `tests/database/test_relationships.py` | Registration creates player nickname and zeroed statistics |
| Seeds | `tests/database/test_seeds.py` | `seed_all` twice yields 3 game modes and 2 item definitions |
| PostgreSQL | `tests/database/test_postgres.py` | Compiled `JSONB`; optional live account round trip |
| Importers | `tests/importers/test_import.py` | Dry run writes nothing, duplicate username skipped, invalid batch rolls back |
| Migrations | `tests/migrations/test_alembic.py` | Upgrade and downgrade on an empty temp file; one active legacy row copied to `accounts.status` `active` and kept in `legacy_players` |
| Security | `tests/security/test_responses.py` | `AccountResponse` omits `password_hash`; `AccountSessionResponse` omits `token_hash`; token response has `access_token` and no `password` |
| Regression | `tests/regression/test_report_compare.py`, `tests/regression/test_runner.py` | Failure classification; test runner refuses `ros_server.db` and writes a player feature report |
| Performance | `tests/performance/test_load.py` | Short Locust run against a temp SQLite file; polls `GET /health` for HTTP 200 before load |
| Management | `tests/management/test_project_control.py` | Registry validation, historical task statuses, no `compatible` features, append-only checkpoints, changelog render, atomic write backup |

Counted test functions: 66. **Confirmed fact** from `def test_` in those files.

## Missing coverage

### Logout

**Confirmed fact.** `app/api/v1/auth.py` exposes `POST /register` and `POST /login` only. No route, service method, or test name contains logout. `tests/integration/test_auth.py` and `tests/compatibility/authentication/test_login.py` stop at login and profile. `AccountSession.revoked_at` exists on `app/models/account.py` and is unused by tests.

**Unknown.** What an original client sent for logout. This repository has no authorized original specification, and this report does not infer one.

### Durable lobby leave

**Confirmed fact.** Durable membership is `LobbyService.open_lobby`, `join`, `create_team`, and `join_team` in `app/services/lobby_service.py`. `app/api/v1/lobby.py` has no leave or delete route. `tests/integration/test_lobby_routes.py` and `tests/repositories/test_account_repository.py` cover join and rejection of a second or full membership. They never remove a `LobbyMember` or `TeamMember`.

**Confirmed fact.** In-memory leave is a different path. `tests/unit/test_gameplay.py` calls `GameEngine.leave_queue` and expects `"Left the lobby"`. `app/networking/websocket.py` handles `lobby.leave` by calling that in-memory queue. `tests/integration/test_websocket.py` sends `lobby.join` only. `tests/unit/test_protocol.py` parses `lobby.join` only.

### Health database readiness

**Confirmed fact.** `app/api/v1/health.py` `GET /health` returns `{"status": "ok"}` and does not open a database session. `GET /version.cfg` returns a file. Callers that only check HTTP 200 are `tests/integration/test_auth.py`, `tests/unit/test_observability.py`, and `tests/performance/test_load.py`. The metrics test asserts the name `ros_database_query_duration_seconds` appears in `/metrics`. That is not a readiness query.

**Unknown.** Whether a future readiness route should fail closed when the database is down. No test defines that contract.

### Suspended accounts

**Confirmed fact.** `app/models/account.py` allows `active`, `suspended`, and `closed`. `AccountService.login` in `app/services/account_service.py` rejects `status != "active"` with the same 401 text as a bad password. `current_account` in `app/api/dependencies.py` rejects a non-active account with 401 `"Player unavailable"`. No test under `tests/` sets `status` to `suspended` or `closed`, and none asserts those 401s. `tests/migrations/test_alembic.py` inserts one legacy row with `is_active` 1 and asserts `accounts.status` `active`. It does not cover an inactive legacy row.

### Session-row assertions

**Confirmed fact.** `AccountService.login` inserts `AccountSession` with `token_hash` and `expires_at`. No test queries `account_sessions`. `tests/security/test_responses.py` only checks that `token_hash` is absent from `AccountSessionResponse` fields. `current_account` decodes the JWT and loads the account. It does not read `AccountSession` or `revoked_at`. Login tests assert token JSON keys and profile access, not a stored hash or expiry.

## Failing assertions

None recorded. Pytest was not run in this QA pass. **Unknown** which assertions the CTO run failed, passed, or skipped.

# Phase 01 — Security, reliability, and core server validation

Execution checkpoint: CP-0003 / PHASE-01-CORE-RELIABILITY

Git HEAD remains `6b7c55cc6a1659169292ce123a8105814b2d13df` on `main`. The working tree is dirty. This phase was not committed and was not pushed.

The security-engineer subagent wrote `docs/engineering/reviews/RO-038-security.md` and approved logout plus session-row checks. The CTO then applied that approval and ran the verification commands. No api-engineer, qa-engineer, performance-engineer, or devops-engineer subagent was launched for RO-039 through RO-045. Those tasks name the owning role, and each completion report says the CTO ran the commands.

RO-035 stays in `review`. RO-009 stays `ready`. RO-011 stays `blocked`. No feature is marked compatible with original Rules of Survival.

## 1. Completed tasks

| Task | Owner | Status | Evidence |
| --- | --- | --- | --- |
| RO-038 | security-engineer | completed | Read-only review. Recommendation: approve. No pytest in the review. |
| RO-039 | api-engineer | completed | Session lookup on HTTP and WebSocket. Logout revokes one hash. |
| RO-040 | qa-engineer | completed | `tests/integration/test_auth_session.py` passed inside the full suite. |
| RO-041 | performance-engineer | completed | `tests/performance/test_load.py`: 1 passed in 13.69s. |
| RO-042 | qa-engineer | completed | `tests/integration/test_websocket_reliability.py` passed inside the full suite. |
| RO-043 | api-engineer | completed | Durable leave, ready, and unready passed in `tests/integration/test_lobby_routes.py`. |
| RO-044 | api-engineer | completed | `GET /health` is unchanged. `GET /ready` passed in `tests/integration/test_health.py`. |

RO-017 and RO-036 were cancelled so the same logout and health work is not implemented a second time. Their history rows were kept.

Registry validation after the update:

```text
OK: 13 agents, 45 tasks
OK: 45 tasks, 10 discoveries, 43 compatibility features
```

## 2. Incomplete tasks

- RO-045 is `blocked`. Docker did not answer, so PostgreSQL was not executed.
- RO-035 is `review`. QA has not approved the Phase 00 baseline.
- RO-009 is `ready`. The database security review file does not exist.
- RO-011 is `blocked` on RO-009.
- RO-012 is `review`.
- RO-013 is `ready`. RO-014, RO-015, RO-016, RO-018, RO-019, RO-029 through RO-034, and RO-037 remain `backlog`.
- RO-019 still covers lobby gaps other than leave and ready. Its description now says not to reimplement those two routes.

Eligible tasks whose dependencies are completed: RO-009 and RO-013.

## 3. Blockers

- RO-045: `docker version` did not return within 12 seconds and was stopped. No local PostgreSQL service was listed. `POSTGRES_TEST_URL` is unset. Port 5432 was not opened. The resolution is an isolated database, then `pytest tests/database/test_postgres.py`. `ros_server.db` must not be that database.
- RO-011: still waiting for the RO-009 review. RO-038 does not close RO-009.

## 4. Files changed

Server and test files in this phase:

- `app/api/dependencies.py`
- `app/api/v1/auth.py`
- `app/api/v1/health.py`
- `app/api/v1/lobby.py`
- `app/core/security.py`
- `app/networking/websocket.py`
- `app/repositories/account_repository.py`
- `app/schemas/lobby.py`
- `app/services/account_service.py`
- `app/services/auth_service.py`
- `app/services/lobby_service.py`
- `tests/integration/test_auth_session.py`
- `tests/integration/test_health.py`
- `tests/integration/test_lobby_routes.py`
- `tests/integration/test_websocket_reliability.py`
- `tests/performance/test_load.py`
- `tools/load_generator/locustfile.py`
- `reports/performance/measured.json`

Records added or updated for this phase:

- `docs/engineering/reviews/RO-038-security.md`
- `docs/architecture/decisions/ADR-0007-session-enforcement.md`
- `docs/engineering/ARCHITECTURE_DECISIONS.md`
- `.cursor/management/tasks.json`
- `.cursor/management/discoveries.json`
- `.cursor/management/changelog.json`
- `.cursor/management/checkpoints.json`
- `.cursor/management/compatibility.json`
- `.cursor/management/decisions.json`
- `.cursor/management/milestones.json`
- `CHANGELOG.md`
- `testdata/reference/compatibility_matrix.json`
- `reports/checkpoints/CP-0003.md`
- `reports/phase-01/PHASE-01_REPORT.md`

Phase 00 files were already dirty at `6b7c55c` and were not rewritten as server code. They include `AGENTS.md`, team and workflow docs, `team.json`, the tracker scripts, and the Phase 00 report directories.

## 5. Database migrations

No revision was added. Alembic head remains `93510e8bf194`. `ros_server.db` was not upgraded, downgraded, or used as a test database.

## 6. Security findings

RO-038, before the code change:

- High: login wrote `account_sessions.token_hash`, `expires_at`, and a null `revoked_at`, then HTTP and WebSocket never read those columns. No logout route existed.
- No critical finding. Argon2 through `PasswordHash.recommended()` and PyJWT `verify_exp` were left in place.
- Approval conditions: one HTTP logout route, revoke only the presented hash, check the row on both HTTP and WebSocket, keep the active-account check, and do not add a socket message.

What landed:

- `POST /api/v1/auth/logout` sets `revoked_at` on that session and commits in the service.
- `current_account` and the WebSocket token lookup both load the row by hash, match `account_id` to the JWT subject, and reject a missing, revoked, or expired row.
- A second live token still works after the first token is revoked.
- `DIS-0010`: two logins in the same second produced the same token because the payload was only `sub`, `iat`, and `exp`, so the unique hash collided. New tokens include `jti`. Decode still accepts a token that has no `jti`, and expiration verification is unchanged.

Residual risk: the login failure limit is still process-local. Suspended and closed accounts have no dedicated test. RO-009 has not reviewed the database foundation.

## 7. WebSocket test evidence

Phase 00 failure: `tests/performance/test_load.py` logged 4 HTTP requests, 0 HTTP failures, then `websocket_auth` raised `WebSocketTimeoutException`. The process exited 1.

The auth timeout was left at 3 seconds. The server log now goes to the test log file instead of an unread pipe. The client reads frames until `auth.ok`, an authentication rejection, or that same timeout, and the timeout becomes `RuntimeError: websocket auth timed out before auth.ok`.

Rerun: `tests/performance/test_load.py` — 1 passed in 13.69s.

`tests/integration/test_websocket_reliability.py` covers one authenticated client, an invalid token, two clients, disconnect, reconnect, and a revoked token. Those tests passed in the focused suite and in the full suite. `DIS-0009` records the harness finding. A full-pipe trace was not captured before the change. The passing rerun is the evidence.

## 8. Lobby integration test results

`tests/integration/test_lobby_routes.py` now sets ready, sets unready, rejects a guest ready call, leaves, and rejects a second leave. It passed inside the 13-test focused suite and the full suite.

Durable leave removes that player's team rows and the lobby member, then recounts `current_players`. Ready requires an open lobby and an existing member. The in-memory queue still uses account ids. Durable membership uses player ids. Those two stores were not combined.

LOB-003 and LOB-005 are locally implemented and their tests pass. Their original-behavior status stays `unknown`.

## 9. PostgreSQL test results

Not executed.

`tests/database/test_postgres.py::test_postgresql_dialect_uses_jsonb` passed as a compiler check. `test_postgres_account_roundtrip` skipped because `POSTGRES_TEST_URL` is unset. `docker version` timed out at 12 seconds. No PostgreSQL Windows service was listed. That is not a PostgreSQL pass.

## 10. Full test summary

| Run | Result |
| --- | --- |
| Phase 00 `python -m pytest -q --tb=line` | 1 failed, 64 passed, 1 skipped, 64.35s |
| Focused auth, lobby, health, and WebSocket suites | 13 passed, 1 warning, 17.65s |
| `tests/performance/test_load.py` | 1 passed, 13.69s |
| `python -m pytest -q --tb=line` | 72 passed, 1 skipped, 6 warnings, 55.80s |

- Previous failure: `tests/performance/test_load.py::test_locust_profile_measures_a_short_run`.
- New failures: none.
- Fixed failure: the Locust WebSocket timeout.
- Skipped: `test_postgres_account_roundtrip`.
- Warnings that remain: Starlette's httpx deprecation notice, and the Python 3.12 SQLite datetime adapter warning in the legacy-player migration test.

## 11. Known issues

- Original Rules of Survival compatibility is unchanged: 0 compatible, 43 unknown. Local implementation rows for logout, account validation, leave, and ready were updated from tests of this server only.
- RO-035, RO-009, RO-011, and RO-012 are not complete.
- The `GET /ready` 503 branch is implemented and was not forced with a broken database.
- The working tree is ahead of the recorded commit only as uncommitted files. Nothing was pushed.
- RO-020's stored implementation counts were not rewritten after the compatibility rows changed.

## 12. Next recommended tasks

1. Security-engineer writes `docs/engineering/reviews/RO-009-security.md`. Leave RO-011 blocked until that review is accepted.
2. QA reviews RO-035 against the baseline report and the command output. The CTO does not complete RO-035.
3. Unblock RO-045 with a disposable PostgreSQL database and `POSTGRES_TEST_URL`. Run Alembic there, then remove the test rows.
4. Start RO-013 from permitted sources. Do not treat this phase's tests as an original client protocol.
5. After RO-011, finish the remaining lobby gaps in RO-019, then the two-client simulator in RO-037.

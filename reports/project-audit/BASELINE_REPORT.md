# Phase 00 baseline

Checkpoint: PHASE-00-BASELINE-COMPLETE
Recorded: 2026-11-10T23:20:00+07:00
Git HEAD: `6b7c55cc6a1659169292ce123a8105814b2d13df` (`main` tracks `origin/main`)
Working tree: dirty. The registries and this report are not in that commit.

This is an inspection of this repository. It is not an original Rules of Survival specification.

Specialist reports, each limited to one file:

- `reports/project-audit/architecture.md`
- `reports/project-audit/database.md`
- `reports/project-audit/api.md`
- `reports/project-audit/tests.md`
- `reports/project-audit/security.md`
- `reports/project-audit/environment.md`

## 1. Current repository status

Confirmed fact. Python `3.12.10` from `.venv\Scripts\python.exe`. The application package is `app/`. Remote `origin` is `https://github.com/vannyakh/RoS_Server.git`. The only commit is `6b7c55c`.

Confirmed fact. No task is `assigned` or `in_progress`. RO-012 is in `review`. RO-009 is `ready`. RO-011 is `blocked` because RO-009 has no security review.

Confirmed fact. No `.apk` or `.aab` file is in the repository.

## 2. Existing working functionality

Confirmed fact. The process is a FastAPI modular monolith. `GET /health` returns `{"status": "ok"}`. Register, login, and `GET /api/v1/players/me` exist. Durable lobby create, join, team create, and team join exist as HTTP routes. `GET /api/v1/lobby` and `GET /api/v1/matches` read the in-memory world. `GET /api/v1/items` lists item definitions. WebSocket `/api/v1/ws` accepts this server's versioned JSON messages. The first message carries the token.

Confirmed fact. The default tick rate is 20 Hz. Positions, the live queue, and live matches stay in `WorldState`. Finished match totals can be written to `player_statistics` after a match ends.

## 3. Missing functionality

Confirmed fact. There is no logout route. HTTP and WebSocket authentication check the JWT and that the account status is `active`. They do not read `account_sessions.token_hash` or `revoked_at`.

Confirmed fact. Durable lobby leave and the ready flag have no route. Leave exists only for the in-memory queue. `GET /health` does not check the database and does not report a version or readiness beyond `status: ok`.

Confirmed fact. `MatchService` and `InventoryService` have no HTTP caller. The live match is free-for-all. Equipment, vehicles, experience rewards, and currency rewards are not applied by the match loop. WebSocket identity is `accounts.id`. Durable lobby membership uses `players.id`.

## 4. Technical debt and risks

Confirmed fact. On 2026-11-10 at 23:13 local time, `python -m pytest -q --tb=line` finished `1 failed, 64 passed, 1 skipped` in 64.35s. The failure is `tests/performance/test_load.py::test_locust_profile_measures_a_short_run`. Locust 2.47.0 ran 2 users for 10 seconds, recorded 4 HTTP requests and 0 HTTP failures, then `websocket_auth` raised `WebSocketTimeoutException: Connection timed out` and Locust exited 1. The skip is `test_postgres_account_roundtrip` because `POSTGRES_TEST_URL` is unset.

Interpretation. The earlier RO-025 note that the load sample did not sustain a 10 second task loop is still accurate. This run also shows the WebSocket receive can block until Locust's own time limit fails the process.

Risk. RO-009 is still open, so the database foundation is not accepted. Docker Compose was not started. Redis in Compose has no password. The Compose database password is the placeholder `CHANGE_ME`.

## 5. Database status

Confirmed fact. A read-only query of `ros_server.db` returned Alembic revision `93510e8bf194`, 32 SQLite tables, 2 accounts, 2 players, and 2 `legacy_players` rows. The 32 tables are the 30 mapped application tables, `legacy_players`, and `alembic_version`.

Confirmed fact. Upgrade of revision `93510e8bf194` renames an old `players` table to `legacy_players` and copies rows. This audit did not run Alembic and did not open PostgreSQL. A listening port is not a PostgreSQL test result.

## 6. API status

Confirmed routes:

| Method | Path |
| --- | --- |
| GET | `/health` |
| GET | `/version.cfg` |
| POST | `/api/v1/auth/register` |
| POST | `/api/v1/auth/login` |
| GET | `/api/v1/players/me` |
| GET | `/api/v1/lobby` |
| POST | `/api/v1/lobby` |
| POST | `/api/v1/lobby/{lobby_id}/members` |
| POST | `/api/v1/lobby/{lobby_id}/teams` |
| POST | `/api/v1/lobby/teams/{team_id}/members` |
| GET | `/api/v1/matches` |
| GET | `/api/v1/matches/{match_id}` |
| GET | `/api/v1/items` |
| WS | `/api/v1/ws` |

These are this server's routes. They are not claimed to be original client endpoints.

## 7. Networking status

Confirmed fact. `app/networking/protocol.py` validates this server's JSON message types. Protocol tests cover that contract. They do not show that an original game client can connect.

Unknown. The original client packet format, encryption, and service endpoints are not in this repository. No packet capture was taken.

## 8. Original RoS research findings

Confirmed fact, public operations notice only. A web search result for the Steam Community news page of app 788260 included an announcement dated April 26, 2022. The quoted notice says Rules of Survival—Steam would stop operations on June 27, 2022 at 15:00, and that account and character data would be deleted after shutdown. Source: https://steamcommunity.com/app/788260/allnews/ . This session did not open that page in a browser and did not download a client.

Interpretation. That notice describes a shutdown. It does not describe authentication, matchmaking, or combat.

Hypothesis. An authorized protocol or content specification may exist outside this repository. None is checked in here.

Unknown. Original account, lobby, matchmaking, movement, weapon, zone, reward, and packet behavior.

Compatibility remains 0 compatible and 43 unknown.

## 9. APK inspection findings

Confirmed fact. No APK, IPA, packet capture, or native library is stored in this repository. No APK was downloaded or unpacked in this audit. Static inspection was not performed because there is no local APK. Certificate pinning, authentication, and protected networking were not bypassed.

## 10. Test coverage and failures

Confirmed fact. The suite result is in section 4. Covered areas include auth, profile, durable lobby create/join/team, the in-memory match, protocol validation, migration copy of `legacy_players`, and the compatibility matrix.

Confirmed gaps, from test source review: logout, durable lobby leave, health database readiness, suspended accounts, and an assertion that login inserts `account_sessions`.

## 11. Recommended architecture changes

No server code was changed in this audit.

Keep the modular monolith and this project's JSON protocol, as ADR-0001 already records. Do not add an official-client protocol from guesswork.

The next code change should be the small vertical slice below, behind tests, without rewriting revision `93510e8bf194`.

## 12. Prioritized next 20 engineering tasks

Rank uses importance, dependency, evidence already in the repo, and whether a test can prove the change. Original compatibility evidence is absent for every row, so none of these raise `compatibility_status` above `unknown`.

| Rank | Task | Why it is next |
| --- | --- | --- |
| 1 | RO-009 Database security review | Blocks RO-011. Still `ready`. |
| 2 | RO-012 Project-control tracker | In `review`. QA has not approved it. |
| 3 | RO-035 Phase 00 baseline | This report. Stays in `review` until QA reads it. |
| 4 | RO-036 Health readiness | `GET /health` does not report version or database connectivity. |
| 5 | RO-019 Lobby leave, list, and ready | Durable leave and ready have no route. |
| 6 | RO-037 Player simulator lobby flow | `tools/player_simulator` does not yet prove create, join, leave, and list. |
| 7 | RO-017 Logout and session revocation | Session hash is stored and never checked. |
| 8 | RO-011 CTO integration review | Blocked until RO-009 is completed with a report. |
| 9 | RO-013 Research index | Keep facts, interpretations, and hypotheses separate. |
| 10 | RO-014 Client and network research | Only from permitted public or user-supplied sources. |
| 11 | RO-015 Game function research | Original combat values stay unknown. |
| 12 | RO-016 Compatibility registry alignment | Matrix counts drifted from the RO-020 summary. Do not mark compatible. |
| 13 | RO-032 Networking evidence for this server | Document this JSON contract, not an official packet. |
| 14 | Fix or quarantine the Locust WebSocket timeout | Recorded failure in `tests/performance/test_load.py`. |
| 15 | RO-029 Movement contract evidence | Local speed is a project rule, not an original value. |
| 16 | RO-030 Combat contract evidence | Local weapon numbers stay test values. |
| 17 | RO-031 Match results contract evidence | Experience and currency are not paid. |
| 18 | RO-018 Experience and progression rewards | Depends on an explicit local rule, not an invented original formula. |
| 19 | RO-033 Client compatibility verdict | Must stay unknown until an authorized reference and a comparison exist. |
| 20 | RO-034 Release readiness | After RO-011. Compose was not started. |

RO-036 and RO-037 were added as `backlog`. They were not implemented.

## 13. Dependencies and blockers

- RO-011 depends on RO-009. RO-009 has no `docs/engineering/reviews/RO-009-security.md`.
- RO-033 cannot become compatible from local tests.
- PostgreSQL execution needs `POSTGRES_TEST_URL` on a disposable database.
- The live `ros_server.db` must not be downgraded. `legacy_players` must not be deleted.
- The working tree is ahead of GitHub only as uncommitted files. This audit did not create a new commit.

## 14. Next milestone and acceptance criteria

Milestone: Account, player, lobby, and a test client. Independently defined. Not an original-client claim.

Acceptance:

1. `GET /health` reports version, whether the database answers a trivial query, and a readiness value. A test covers a reached database and does not print secrets.
2. Register, login, and profile stay green. Logout revokes the stored session hash, with a test that a revoked session is rejected.
3. A test room can be created, joined, listed, and left by the authenticated player.
4. The player simulator runs at least two test clients through that lobby flow and checks server state.
5. The automated report records pass, fail, and skip. The current Locust failure is either fixed with a new measurement or explicitly excluded with the reason.

Manual action still required: QA review of RO-012 and RO-035, the security engineer for RO-009, and a decision to commit these audit files.

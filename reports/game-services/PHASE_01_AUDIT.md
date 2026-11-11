# Phase 01 audit — repository and API

Recorded: 2026-11-11
Branch: `main`
HEAD: `7affe25`
Python: 3.12.10 from the project virtual environment

This note is an inspection of this repository. It is not an original Rules of Survival specification. No decompiled client file, Android project, or iOS project was modified. The live database file was not migrated, reset, or deleted.

## Registry

Confirmed fact. No task is `assigned` or `in_progress`. Active file ownership is therefore not locked. RO-009 is `ready`. RO-011 is `blocked`. RO-012 is `review`. The CTO registry was not edited. Suggested ids ROS-SVC-001 through ROS-SVC-010 were not added, because `tasks.json` is owned by the CTO.

Confirmed fact. Alembic head in `migrations/versions/` is revision `93510e8bf194`. No new revision was required for the follow-up code in this session.

## What the older baseline no longer describes

Confirmed fact. `reports/project-audit/BASELINE_REPORT.md` says logout, session-hash checks, durable leave, ready, and database readiness are missing. The code inspected at the start of this session already had:

- `POST /api/v1/auth/logout`
- session lookup by SHA-256 hash, including `revoked_at` and `expires_at`
- `DELETE /api/v1/lobby/{lobby_id}/members` and `POST /api/v1/lobby/{lobby_id}/ready`
- `GET /ready` executing `SELECT 1`
- `POST /api/v1/match-records` for the stored lifecycle
- inventory and currency routes
- WebSocket authentication through `AccountService.account_for_token`

Interpretation. The baseline is a historical snapshot. The route table in `docs/API_CONTRACT.md` is the current contract.

## Layout

Confirmed fact. The application is one FastAPI package under `app/`. Routers are registered in `app/api/router.py`. Services are modules under `app/services/`, not nested packages such as `app/services/auth/`. Repositories, models, and schemas already exist. Live match state is `WorldState` inside `app/game/`. The tick is started from `app/main.py`.

The target tree in the game-services plan was not applied as a file move. Working imports were left in place. The logical mapping is `docs/SERVICE_ARCHITECTURE.md`.

## Gaps found before the code changes

Confirmed fact, from reading the services and models:

1. `PlayerUpdate` existed and had no route.
2. A member could not read a durable lobby or its member list.
3. Join checked capacity in Python before insert, so two concurrent joins could pass a one-seat lobby.
4. The last member to leave did not close the lobby.
5. `teams` and `lobby_members` have no leader column.
6. A player could be a participant in two stored matches that were still `scheduled`, `lobby`, or `running`.
7. `MatchService.finalize` stores `rewards` and does not change experience, currency, or `player_statistics`.
8. WebSocket identity is the account id. Durable membership uses the player id.
9. `GET /api/v1/lobby` is the in-memory queue, not the durable table.
10. Equipment ownership is not modeled. `equipment_definitions` is only a catalog.
11. Matchmaking is in-memory and single-process. There is no HTTP queue and no Redis matchmaker.
12. PostgreSQL execution is skipped unless `POSTGRES_TEST_URL` is set.
13. `/items`, `/metrics`, `GET /lobby`, and `GET /matches` do not require a session.
14. `POST /inventory/items` and `POST /inventory/currency` let a player change their own rows directly.

Hypothesis. The baseline WebSocket load timeout was a SQLite lock or a dropped socket during session lookup. It was not reproduced. The suite in this session included that load test and it passed. See `reports/game-services/IMPLEMENTATION_REPORT.md`.

Unknown. Original account, lobby, matchmaking, combat, equipment, and reward behavior.

## Follow-up in this session

The safe gaps that already had a schema or a local rule were implemented after this inspection:

- `PATCH /api/v1/players/me`
- `GET /api/v1/lobby/{lobby_id}` and `GET /api/v1/lobby/{lobby_id}/members`
- conditional capacity update and closing an empty lobby
- one active stored match per player
- SQLite busy wait of 5 seconds
- WebSocket session-lookup failures return an auth error instead of an unlogged handler crash
- tests for logout's neighboring cases, lobby rules, reward non-application, and a second socket

Leader permissions, equipment slots, and reward payouts were not invented. Rewards stay unimplemented, with a test that a `rewards` payload does not change level, kills, matches played, or currency.

## Verification at audit time

The full command was run after the follow-up code, not before it:

`python -m pytest -q --tb=line`

Result: 89 passed, 1 skipped, 6 warnings, 76.43s. The skip is `test_postgres_account_roundtrip` because `POSTGRES_TEST_URL` is not set. No test was deleted or skipped to obtain that result.

Compatibility remains 0 compatible and 43 unknown.

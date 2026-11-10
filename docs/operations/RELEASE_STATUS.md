# Release status

Recorded 2026-11-10. This is not a release.

## What is running

- Alembic head is `93510e8bf194`.
- Development storage is SQLite. Production startup does not migrate itself.
- Original compatibility is 0 compatible. Local tests are not that verdict.
- Redis is optional and is not required at startup.

## What was not executed

- Docker Desktop returned HTTP 500 from its engine API. Compose was not started.
- `POSTGRES_TEST_URL` is unset. The PostgreSQL roundtrip remains skipped.
- `ros_server.db` was not copied, upgraded, downgraded, or used as a test database.
- RO-011 stays blocked until the RO-009 database security review exists.

## Backup

Stop the server before copying the SQLite file so the copy is not taken while a write is open. Copy `ros_server.db` to a path that stays out of git. `*.db` is already ignored. Do not delete `legacy_players` or player-owned rows. Do not run `alembic downgrade` on the live file. A copy is a file backup, not proof that PostgreSQL restore works.

Registry JSON files already get timestamped copies under `.cursor/management/backups/` when the tracker writes them. Those copies are not the game database.

## Load sample

`reports/performance/measured.json` is the latest short Locust sample. It is not a capacity result. `MAX_PLAYERS_PER_MATCH` is a configuration cap, not a measured limit.

## Before a release

1. Finish the RO-009 review and then RO-011.
2. Run Alembic and the account roundtrip on a disposable PostgreSQL database.
3. Take a stopped-server copy of the SQLite file before any production cutover.
4. Keep every compatibility row unknown until an authorized reference and a comparison exist.

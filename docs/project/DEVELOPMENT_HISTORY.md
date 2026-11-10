# Development history

This page summarizes records that already exist. The changelog in `.cursor/management/changelog.json` is the change history from the project-control system onward. Older task evidence stays on each task.

## Database foundation

RO-001 inspected the repository. The old database was one `players` table. Inventory, matches, and sessions were in memory.

RO-002 recorded the database architecture. RO-003 added the SQLAlchemy models. RO-004 added Alembic revision `93510e8bf194`, which renames the old table to `legacy_players` and does not drop it on upgrade. RO-005 added seeds and the importer. RO-008 recorded database QA. RO-010 documented PostgreSQL, Redis, backup, and the fact that Compose was not started.

RO-009, the security review, is ready and has no report yet. RO-011 stays blocked until that review is complete.

## Services and local match rules

RO-006 and RO-007 recorded schemas and the service foundation. The server has local account, player, lobby, matchmaking, movement, combat, and result behavior. RO-020's stored summary says 26 implemented, 10 partial, and 7 not implemented. The compatibility file now counts 29 implemented, 7 partial, and 7 not implemented. That task report was not rewritten. None of the 43 features are marked compatible with original Rules of Survival.

## Quality tools

RO-021 through RO-027 recorded the test runner, deterministic simulator, function tracker, protocol validator, Locust sample, monitoring docs, and regression reports. RO-028 reviewed that work. The recorded suite was 54 passed and 1 skipped. The skip is the PostgreSQL round-trip. The Locust sample did not sustain a 10 second task rate.

## Project control

RO-012 adds the research, compatibility, checkpoint, and changelog registries. It is in review until QA runs `python scripts/validate_project_management.py`.

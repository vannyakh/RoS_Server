# Database implementation plan

## Existing architecture

The server already had one SQLAlchemy async engine in `app/infrastructure/database.py`. Development used `sqlite+aiosqlite:///./ros_server.db`. PostgreSQL and Redis were named in Compose and were not required to boot.

The only mapped table was `players`: `id`, `username`, `password_hash`, `is_active`, `kills`, `wins`, `matches_played`. `inventory.py`, `match.py`, and `session.py` were in-memory dataclasses, not tables. Alembic was installed and had no `alembic.ini`, `env.py`, or revisions. Startup called `create_all` and a SQLite `ALTER TABLE` helper for the stat columns.

Register, login, `/players/me`, and the end-of-match stat write all used that one row. The 20 Hz simulation does not write SQL. Stats are saved only after a match produces a result.

## Problems

- Credentials and match totals shared one table, so a profile could not grow without widening the login row.
- There were no foreign keys, timestamps, or check constraints.
- `create_all` cannot change an existing production table safely, and the `ALTER TABLE` helper was SQLite-only.
- Password hashes lived on the same object the profile route loaded.
- Inventory, lobby membership, and match history could not be stored or constrained.
- Reference data, imports, and migrations did not exist.

## Model relationships

One account has one player. The player owns statistics, progression, one inventory, and currency balances. Lobby membership, team membership, and match participation point at the player. A match points at an optional game mode and map. Inventory rows point at item definitions. Live coordinates stay in memory.

Account ids stay the JWT `sub` and the `id` returned by register, so existing clients keep working. The profile id is a separate `players.id`.

## Migration strategy

Revision `93510e8bf194` creates the normalized schema. If it finds the old `players` table (a `password_hash` column and no `account_id`), it renames that table to `legacy_players`, builds the new tables, and copies each old row into `accounts`, `players`, and `player_statistics`. The upgrade does not drop `legacy_players`. Downgrade drops the new tables and renames `legacy_players` back only when `players` is already gone. Downgrade was run on disposable SQLite files, not on the development database.

## Implementation sequence

1. Inspect the models, auth flow, and startup path.
2. Add portable UUID strings, timestamps, and a JSON/JSONB column type.
3. Add account, player, and reference models.
4. Add inventory, lobby, match, and configuration models.
5. Generate and review the Alembic revision, including the legacy copy.
6. Add idempotent seeds and a dry-run importer.
7. Point auth, profile reads, and match-result saves at the new tables.
8. Test constraints, relationships, migrations, seeds, imports, and repositories on SQLite.
9. Compile the PostgreSQL dialect separately. A live PostgreSQL run happens only when `POSTGRES_TEST_URL` is set.

## Testing strategy

`pytest` uses `sqlite+aiosqlite:///./test_ros.db`, drops it, and applies the revision. Migration tests use temporary files, including a hand-built legacy `players` table. Import tests check dry-run, duplicate usernames, and rollback. PostgreSQL is skipped unless `POSTGRES_TEST_URL` is set; SQLite results are not treated as a PostgreSQL pass.

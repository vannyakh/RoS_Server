# Database audit

Read-only inspection on 2026-11-10. Models, migrations, `tasks.json`, and `ros_server.db` were not modified. Alembic upgrade and downgrade were not run. The only write is this file.

Labels:

- **Confirmed fact** — read from a file or from a read-only query in this audit.
- **Interpretation** — conclusion from those facts, not a separate measurement.
- **Hypothesis** — plausible, and not demonstrated by a run.
- **Unknown** — not established by the files or by this audit.

## Tables

**Confirmed fact.** `app/models/__init__.py` exports 30 mapped classes. Revision `93510e8bf194` creates the same 30 tables in `migrations/versions/93510e8bf194_initial_database_schema.py`. `legacy_players` is not a mapped class and is not created with `op.create_table`.

| Group | Tables | Source |
| --- | --- | --- |
| Accounts | `accounts`, `account_sessions`, `account_devices`, `login_history` | `app/models/account.py` |
| Players | `players`, `player_statistics`, `player_progression` | `app/models/player.py` |
| Inventory | `player_inventories`, `inventory_items`, `player_currencies`, `currency_transactions` | `app/models/inventory.py` |
| Catalog | `game_modes`, `map_definitions`, `item_definitions`, `weapon_definitions`, `equipment_definitions`, `vehicle_definitions`, `rank_definitions`, `achievement_definitions` | `app/models/game_data.py` |
| Matches | `matches`, `match_participants`, `match_results`, `match_statistics` | `app/models/match.py` |
| Lobbies | `lobbies`, `lobby_members`, `teams`, `team_members` | `app/models/lobby.py` |
| Settings | `server_configurations`, `game_configurations`, `feature_configurations` | `app/models/configuration.py` |

**Confirmed fact.** Primary keys are `String(36)` from `IdMixin` (`app/models/types.py`). The revision stores those ids as `sa.String(length=36)`.

**Confirmed fact.** Relationships in the model modules above use `lazy="raise"`.

**Confirmed fact.** JSON documents use `PortableJSON` (`app/models/types.py`): `JSON().with_variant(JSONB(), "postgresql")`. Catalog `metadata`, configuration `value`, `currency_transactions.metadata`, `match_results.rewards`, and `match_statistics.summary` use that type. The attribute name for a column named `metadata` is `details`.

**Confirmed fact.** `matches`, `match_participants`, `match_results`, and `match_statistics` have no position or aim columns (`app/models/match.py`). `app/models/lobby.py` states that high-frequency movement is not stored on lobby tables.

**Confirmed fact.** Non-negative and status checks in the models are emitted in the revision, including `ck_accounts_status`, `ck_players_level`, `ck_player_currencies_balance`, `ck_inventory_items_quantity`, `ck_matches_status`, and the participant and statistics checks. `currency_transactions.amount` has no check constraint (`app/models/inventory.py`).

**Confirmed fact.** Child foreign keys set `ondelete` in both the models and the revision: `CASCADE` for owned rows, `SET NULL` for `login_history.account_id`, `lobbies.game_mode_id`, `weapon_definitions.item_definition_id`, and `match_participants.team_id`, and `RESTRICT` for `matches.game_mode_id`, `matches.map_id`, and `inventory_items.item_definition_id`.

**Confirmed fact.** A read-only query of `ros_server.db` (`file:...?mode=ro`) listed 32 tables: the 30 application tables, `legacy_players`, and `alembic_version`. `alembic_version` is `93510e8bf194`. Counts were `accounts` 2, `players` 2, `legacy_players` 2. Usernames and password hashes were not read.

## Indexes

**Confirmed fact.** Lookup indexes declared on the models and created in revision `93510e8bf194`:

| Index | Table | Columns | Unique |
| --- | --- | --- | --- |
| `ix_accounts_status` | `accounts` | `status` | no |
| `uq_account_devices_account_device` | `account_devices` | `account_id`, `device_identifier` | yes |
| `ix_account_sessions_account_expires` | `account_sessions` | `account_id`, `expires_at` | no |
| `ix_login_history_account_created` | `login_history` | `account_id`, `created_at` | no |
| `ix_players_status` | `players` | `status` | no |
| `ix_currency_transactions_player_id` | `currency_transactions` | `player_id` | no |
| `ix_matches_status_created_at` | `matches` | `status`, `created_at` | no |
| `ix_match_participants_player_id` | `match_participants` | `player_id` | no |
| `ix_lobby_members_player_id` | `lobby_members` | `player_id` | no |
| `ix_teams_lobby_id` | `teams` | `lobby_id` | no |
| `ix_team_members_player_id` | `team_members` | `player_id` | no |

**Confirmed fact.** Uniqueness is also enforced with table constraints, including `accounts.username`, `accounts.email`, `players.nickname`, `uq_players_account_id`, `uq_player_statistics_player_id`, `uq_player_progression_type`, `uq_player_inventories_player_id`, `uq_inventory_items_player_item`, `uq_player_currencies_code`, `account_sessions.token_hash`, `matches.match_code`, `uq_match_participants_player`, `uq_match_results_player`, `uq_match_statistics_match_id`, `lobbies.code`, `uq_lobby_members_player`, `uq_teams_lobby_code`, `uq_team_members_player`, `uq_team_members_lobby_player`, configuration keys, and catalog `code`.

**Confirmed fact.** `app/infrastructure/database.py` sets the naming convention `ix_%(column_0_label)s`, `uq_%(table_name)s_%(column_0_name)s`, `ck_%(table_name)s_%(constraint_name)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`, `pk_%(table_name)s`. Explicit constraint names in the models override the single-column default where a pair is unique.

## `legacy_players` preservation

**Confirmed fact.** Upgrade calls `preserve_legacy_players` before creating tables and `copy_legacy_players` after creating them (`93510e8bf194_initial_database_schema.py` lines 23–24 and 466). Downgrade drops the new tables, including the new `players` table, and then calls `restore_legacy_players` (lines 469–535). `downgrade()` does not call `op.drop_table('legacy_players')`.

**Confirmed fact.** `migrations/legacy_players.py` implements the rule:

- `preserve_legacy_players` renames `players` to `legacy_players` only when `players` exists, has `password_hash`, and has no `account_id`. Otherwise it returns.
- `copy_legacy_players` returns when `legacy_players` is absent. For each row it inserts an `accounts` row with the legacy id, a new `players` id, and `player_statistics` (`total_matches`, `total_wins`, `total_kills` from `matches_played`, `wins`, `kills`). It skips a row when that account id already exists. It does not delete the legacy row.
- `is_active` in `(1, True, "1")` becomes account status `active`. Any other value becomes `suspended`.
- `restore_legacy_players` renames `legacy_players` back to `players` only when `legacy_players` exists and `players` does not.

**Confirmed fact.** The live `legacy_players` columns are `id`, `username`, `password_hash`, `is_active`, `kills`, `wins`, `matches_played`, which matches the `SELECT` in `copy_legacy_players`.

**Confirmed fact.** `docs/DATABASE_OPERATIONS.md` says an upgrade of the existing development database keeps old login rows by copying them and does not drop `legacy_players`. It also says downgrade is for a copy or a temporary file and drops `accounts`, `players`, and the other new tables.

**Confirmed fact.** `.cursor/management/tasks.json` RO-004 `completion_report.migration_results` records that `ros_server.db` is at `93510e8bf194`, that legacy rows were copied, and that downgrade was not run on `ros_server.db`. This audit did not re-run that migration. It did confirm the revision id and that `legacy_players` is still present.

**Interpretation.** Identity continuity for a copied login is the account id, which reuses the legacy id. The new `players.id` is a new UUID, so the profile id changes.

**Interpretation.** `migrations/env.py` passes `Base.metadata` to Alembic and does not exclude `legacy_players`. A later autogenerate can propose dropping that table because it is not mapped. That proposal is not in the current revision.

## SQLite and PostgreSQL

**Confirmed fact.** `app/models/types.py` says UUID strings are used so one migration serves SQLite and PostgreSQL. `PortableJSON` compiles to `JSON` and to PostgreSQL `JSONB`. The revision repeats that variant: `sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')`.

**Confirmed fact.** `app/core/config.py` defaults `database_url` to `sqlite+aiosqlite:///./ros_server.db`. `alembic.ini` sets `sqlalchemy.url` to the same SQLite URL. `migrations/env.py` does not read that ini URL. `database_url()` uses `DATABASE_URL` from the process environment, then `settings.database_url`.

**Confirmed fact.** `migrations/env.py` sets `PRAGMA foreign_keys=ON` only when `connection.dialect.name == "sqlite"`. Online and offline migrations set `render_as_batch=True` for every dialect. `app/infrastructure/database.py` uses `NullPool` when the URL starts with `sqlite`, and `pool_pre_ping=True`, `pool_size=10`, `max_overflow=20` otherwise. The same module sets the SQLite foreign-key pragma on connect only for a SQLite URL.

**Confirmed fact.** `init_db()` in `app/infrastructure/database.py` runs `alembic upgrade head` only when `settings.app_env == "development"`. Any other environment returns without migrating. This audit did not start the application.

**Confirmed fact.** `docs/DATABASE_OPERATIONS.md` says the test run does not start PostgreSQL. Without `POSTGRES_TEST_URL`, `tests/database/test_postgres.py` is skipped, and a skip is not a PostgreSQL pass. It says `test_postgresql_dialect_uses_jsonb` only checks that the PostgreSQL compiler emits JSONB.

**Confirmed fact.** `tests/database/test_postgres.py` skips `test_postgres_account_roundtrip` when `POSTGRES_TEST_URL` is unset, with the reason "PostgreSQL was not executed". The JSONB test compiles `ItemDefinition` with `postgresql.dialect()` and does not open a connection.

**Confirmed fact.** `tests/migrations/test_alembic.py` upgrades and downgrades disposable SQLite files, including a hand-built legacy `players` table. Those tests are SQLite paths.

**Confirmed fact.** `.cursor/management/tasks.json` RO-008 records `34 passed, 1 skipped` on 2026-11-10. The skip is `test_postgres_account_roundtrip`. The same report says the JSONB test passed as a compile check only, and "This does not certify PostgreSQL execution." Later recorded full-suite lines through RO-028 repeat `54 passed, 1 skipped` for the same skip reason. This audit did not re-run pytest.

**Confirmed fact.** `docker-compose.yml` defines a `postgres:17` service and a `DATABASE_URL` of `postgresql+asyncpg://ros:CHANGE_ME@postgres:5432/ros`. That file is a service definition. This audit did not run Compose.

**Interpretation.** SQLite is the database the application default, Alembic ini, development file, and recorded migration tests actually use. PostgreSQL support in this tree is dialect compilation, pool settings, and a test that connects only when `POSTGRES_TEST_URL` is set.

**Hypothesis.** Revision `93510e8bf194` can upgrade a PostgreSQL database because keys are strings, JSON is variant-compiled to JSONB, and batch mode is enabled for every dialect. No recorded live PostgreSQL result confirms that.

## Whether PostgreSQL was executed

**Confirmed fact.** The recorded suite did not execute the live PostgreSQL roundtrip. RO-008 and `docs/DATABASE_OPERATIONS.md` both say a skip is not a PostgreSQL pass. The JSONB check does not connect to a server.

**Confirmed fact.** This audit did not set `POSTGRES_TEST_URL`, did not open a PostgreSQL connection, and did not run Alembic against any database.

**Confirmed fact.** During this audit, local TCP port 5432 was in the Listen state. The process name was not identified, and no session was opened to it.

**Unknown.** Whether that listener is PostgreSQL, whether it is the Compose service, and whether revision `93510e8bf194` has ever been applied to a PostgreSQL database. `.env` was not read, so an override of `DATABASE_URL` was not inspected. The on-disk development database that was inspected is the SQLite file `ros_server.db`.

## Sources

- `app/models/__init__.py`, `app/models/types.py`, `app/models/account.py`, `app/models/player.py`, `app/models/inventory.py`, `app/models/game_data.py`, `app/models/match.py`, `app/models/lobby.py`, `app/models/configuration.py`
- `app/infrastructure/database.py`
- `app/core/config.py`
- `migrations/env.py`
- `migrations/legacy_players.py`
- `migrations/versions/93510e8bf194_initial_database_schema.py`
- `alembic.ini`
- `docs/DATABASE_OPERATIONS.md`
- `tests/database/test_postgres.py`
- `tests/migrations/test_alembic.py`
- `docker-compose.yml`
- `.cursor/management/tasks.json` (RO-004, RO-008, and later skip notes)
- Read-only `sqlite3` query of `ros_server.db` (`mode=ro`): table list, `alembic_version`, `legacy_players` column names, and three row counts

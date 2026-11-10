# Database operations

## Fresh development database

```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
alembic current
python -m app.database.seeds.seed_all
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Development startup runs `alembic upgrade head` in a subprocess, then the server continues. Production startup does not migrate. Apply the revision before starting a production process.

`alembic history` shows `93510e8bf194` as the initial schema.

## Existing development database

Stop the server so SQLite is not locked, then:

```powershell
alembic upgrade head
python -m app.database.seeds.seed_all
```

That keeps the old login rows by copying them. It does not drop `legacy_players`.

## Disposable downgrade

```powershell
alembic downgrade -1
alembic upgrade head
```

Use this on a copy or a temporary file. Downgrade drops `accounts`, `players`, and the other new tables.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

PostgreSQL is not started by the test run. To exercise it:

```powershell
$env:POSTGRES_TEST_URL = "postgresql+asyncpg://ros:CHANGE_ME@127.0.0.1:5432/ros"
.\.venv\Scripts\python.exe -m pytest tests/database/test_postgres.py -q
```

Without `POSTGRES_TEST_URL`, that test is skipped. A skipped result is not a PostgreSQL pass. `test_postgresql_dialect_uses_jsonb` only checks that the PostgreSQL compiler emits JSONB.

## Pooling

SQLite uses a null pool. PostgreSQL uses `pool_pre_ping`, pool size 10, and max overflow 20. Redis is still optional and is not opened during startup. Lobby presence for the live match stays in memory; the `lobbies` tables are the durable roster, not the 20 Hz world.

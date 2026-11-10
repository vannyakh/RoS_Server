---
name: alembic-migrations
description: Creates and verifies Alembic revisions for the async SQLite and PostgreSQL setup. Use when models change and migrations/versions needs a new revision.
---

# Alembic migrations

## When

`app/models` changed and the database must gain a reviewed revision.

## Input

The model diff and a disposable database URL. Never take `ros_server.db` as the downgrade target.

## Workflow

1. Confirm `migrations/env.py` still reads `DATABASE_URL` before settings.
2. Generate from the project root:

```powershell
alembic revision --autogenerate -m "describe_the_change"
```

3. Read the generated file. Remove accidental drops of `legacy_players`, `accounts`, or `players`.
4. Apply and reverse on a temporary file:

```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///./tmp_migration.db"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

5. Delete the temporary file after the commands succeed.
6. For an existing development database, stop the server, copy the `.db` file, then `alembic upgrade head`. Do not downgrade that copy unless the user approved it.

## Checklist

- Revision has `upgrade` and `downgrade`
- No `create_all` added to startup
- Disposable downgrade was run
- Applied revision `93510e8bf194` was not edited

## Output

Revision id, upgrade output, downgrade output, and any data-preserving branch.

## Failure

If autogenerate drops a populated table, delete the new unapplied revision and write the operation by hand. If the temporary downgrade fails, leave the task blocked and include the error.

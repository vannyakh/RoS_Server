---
name: data-import
description: Runs idempotent seeds and the batch importer with dry-run, validation, and rollback. Use for app/database/seeds, app/database/importers, or data/migration files.
---

# Data import

## When

Reference data or a user-owned JSON/CSV dataset must enter the database.

## Input

A source directory and either `--dry-run` or `--commit`. Schema version in each JSON file must be `1`.

## Workflow

1. Seed catalogs by stable code. Running the seed twice must not insert a second row.

```powershell
python -m app.database.seeds.seed_all
```

2. Validate the source with a dry run before commit:

```powershell
python -m app.database.importers.import_data --source .\data\migration --dry-run
```

3. Commit only after the dry run reports no errors. Existing usernames are skipped. Do not overwrite balances.
4. On any record error, the commit path rolls back the whole batch.
5. Refuse datasets obtained by bypassing another game's authentication.

## Checklist

- Codes are stable and original to this project
- Dry run executed before commit
- Duplicate usernames skipped
- Player-owned rows were not deleted

## Output

The import report: created, skipped, and errors.

## Failure

If validation fails, leave the database unchanged and return the report. Do not switch to commit to "see what happens."

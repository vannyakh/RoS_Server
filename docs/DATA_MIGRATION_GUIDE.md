# Data migration guide

## Legacy login table

Databases created before this revision have a `players` table with `username` and `password_hash`. `alembic upgrade head` renames that table to `legacy_players` and copies:

- `id`, `username`, and `password_hash` into `accounts` (the same id, so existing tokens still match)
- a new `players` profile whose nickname is the username
- `kills`, `wins`, and `matches_played` into `player_statistics`

The old table is left in place as `legacy_players`. The upgrade does not delete it. Import and seed commands also do not delete player-owned rows.

`alembic downgrade base` drops the new tables. If `legacy_players` is still there and `players` is not, the downgrade renames it back. Run that only on a copy. It was tested on temporary SQLite files.

## Import files

Put JSON (or CSV for the same record names) under a source directory:

- `accounts.json` with `accounts`: `username`, `password`, optional `email`
- `players.json` with `players`: `username`, `nickname` (skipped when that account already has a profile)
- `items.json` with `items`: `code`, `name`
- `inventory.json` with `inventory`: `nickname`, `item_code`, `quantity`

Every JSON file needs `"schema_version": 1`. Passwords in the file are hashed on the way in and are not stored as plaintext. An existing username is skipped. Currency balances are not replaced by the importer.

```powershell
python -m app.database.importers.import_data --source .\data\migration --dry-run
python -m app.database.importers.import_data --source .\data\migration --commit
```

`--commit` rolls the whole run back when any record has an error. Do not point the importer at data taken from another game's private backend.

## Seeds

```powershell
python -m app.database.seeds.seed_all
```

The command upserts development fixtures by code. Running it again does not add a second `SOLO` or `TEST_ITEM`.

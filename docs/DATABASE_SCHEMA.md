# Database schema

Revision: `93510e8bf194` (`initial_database_schema`).

Primary keys are UUID strings (`VARCHAR(36)`) so SQLite and PostgreSQL share one revision. Timestamps are UTC. The attribute `details` is stored in a column named `metadata` because SQLAlchemy reserves `metadata` on the model class. That column is JSON on SQLite and JSONB on PostgreSQL.

High-frequency positions, aim, and health are not columns. The simulation keeps them in memory. `player_statistics` is updated only when a match result is ready.

## Accounts

| Table | Purpose | Integrity |
|---|---|---|
| `accounts` | Login identity | Unique `username` and `email`; `status` is `active`, `suspended`, or `closed` |
| `account_sessions` | Hash of an issued access token | Unique `token_hash`; indexed by account and expiry |
| `account_devices` | Device seen for an account | Unique `(account_id, device_identifier)` |
| `login_history` | Success and failure attempts | `account_id` is null when the username did not match |

`password_hash` and `token_hash` are not part of any response schema.

## Players

| Table | Purpose | Integrity |
|---|---|---|
| `players` | One profile per account | Unique `account_id`, unique `nickname`, `level >= 1`, `experience >= 0` |
| `player_statistics` | Lifetime totals | One row per player; totals are non-negative |
| `player_progression` | Named progression track | Unique `(player_id, progression_type)` |

## Reference data

`game_modes`, `map_definitions`, `item_definitions`, `weapon_definitions`, `equipment_definitions`, `vehicle_definitions`, `rank_definitions`, and `achievement_definitions` are catalogs. Each has a unique `code`. Seeds use `SOLO`, `DUO`, `SQUAD`, `TEST_MAP`, `TEST_ITEM`, and other `TEST_*` codes. Those codes are development fixtures.

## Inventory

| Table | Purpose | Integrity |
|---|---|---|
| `player_inventories` | One inventory per player | Unique `player_id` |
| `inventory_items` | Stack of one item definition | Unique `(inventory_id, item_definition_id)`, `quantity >= 0` |
| `player_currencies` | Named balance | Unique `(player_id, currency_code)`, `balance >= 0` |
| `currency_transactions` | Ledger row for each change | `balance_after` is the balance after that row |

## Matches, lobbies, configuration

| Table | Purpose | Integrity |
|---|---|---|
| `matches` | Durable match header | Unique `match_code`; index on `(status, created_at)`; status check |
| `match_participants` | One join per player | Unique `(match_id, player_id)` |
| `match_results` | Final placement | Unique `(match_id, player_id)` |
| `match_statistics` | One summary per match | Unique `match_id` |
| `lobbies` | Durable lobby header | `max_players > 0` |
| `lobby_members` | Membership | Unique `(lobby_id, player_id)` |
| `teams` | Team inside a lobby | Unique `(lobby_id, code)` |
| `team_members` | Team roster | Unique per team and unique per lobby |
| `server_configurations`, `game_configurations` | Versioned key/value settings | Unique key |
| `feature_configurations` | Feature flag | Unique `code` |

Lobby capacity and match state transitions are enforced in the service layer as well as by these checks. Capacity cannot be expressed as a single-row check against the member count.

## Index choices

Unique keys cover the lookups used by login, nickname, item code, and “is this player already in this match/lobby?”. `ix_matches_status_created_at` serves the recent-match list. `ix_login_history_account_created` serves account history. Foreign keys are indexed. Large collections use `lazy="raise"` so a request must opt in with `selectinload` instead of issuing a query per row by accident.

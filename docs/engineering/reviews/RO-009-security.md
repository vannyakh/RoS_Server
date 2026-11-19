TASK ID: RO-009
AGENT: security-engineer
PHASE: 03
STATUS: review

IMPLEMENTATION: Read-only review. No application code, tests, migrations, environment files, or task registry files were modified.
FILES CREATED: docs/engineering/reviews/RO-009-security.md
FILES MODIFIED: none
DISCOVERIES: Account passwords go through Argon2. Session tokens are stored as SHA-256 hashes. Response schemas omit password_hash and token_hash. The account importer skips existing usernames and stores a hash. Upgrade 93510e8bf194 does not drop legacy_players. Login responses for an unknown user, a bad password, and an inactive account use the same 401 detail. Three medium gaps remain: password verification is skipped for a missing user, operator login has no failure limit, and token checks use a different 401 detail for an inactive account.
DATABASE CHANGES: none
API CHANGES: none
GAME FUNCTION CHANGES: none
TESTS EXECUTED: python scripts/validate_agent_registry.py
TEST RESULTS: Exit code 0. Output: OK: 13 agents, 55 tasks. This registry check is not a security pass.
COMPATIBILITY EVIDENCE: not applicable. This review does not mark any feature compatible with original Rules of Survival.
KNOWN ISSUES: Missing-user login skips password verification. Operator login is not covered by the in-memory failure limit. A decoded token for a missing or inactive account returns a different 401 detail than an invalid session. Copied legacy password hashes were not re-checked against live rows. Downgrade of 93510e8bf194 drops the new player-owned tables.
RECOMMENDATION: approve

OBJECTIVE: Independently review account storage, session hashes, response schemas, importer behavior, and migration safety for RO-009.
IMPLEMENTATION SUMMARY: The review opened the account model, password and token helpers, response schemas, account and operator login paths, HTTP and WebSocket session checks, the account importer, and the legacy upgrade. Findings below cite those files. No secret, password hash, raw token, or session hash is included.
SECURITY CONSIDERATIONS: Required storage and schema controls are present. Medium findings are follow-up hardening. They do not show hash fields in responses, plaintext passwords written by the importer, or a drop of legacy_players on upgrade.
DEPENDENCIES: RO-003 and RO-004 are the task dependencies. This report does not change task status. The CTO records the result.

# RO-009 database security review

Reviewer: security-engineer. Scope was read-only. STATUS in this report is review because the registry was not edited.

## Files read

- .cursor/skills/security-audit/SKILL.md
- .cursor/rules/04-security.mdc
- .cursor/agents/security-engineer.md
- .cursor/management/tasks.json
- .cursor/management/workflow.json
- app/models/account.py
- app/core/security.py
- app/core/config.py
- app/schemas/__init__.py
- app/schemas/account.py
- app/schemas/auth.py
- app/schemas/player.py
- app/schemas/common.py
- app/schemas/inventory.py
- app/schemas/cosmetics.py
- app/schemas/configuration.py
- app/schemas/game_data.py
- app/schemas/lobby.py
- app/schemas/match.py
- app/schemas/maps.py
- app/services/account_service.py
- app/services/auth_service.py
- app/services/operator_service.py
- app/services/inventory_service.py
- app/api/v1/auth.py
- app/api/v1/admin_access.py
- app/api/v1/admin_support.py
- app/api/dependencies.py
- app/networking/websocket.py
- app/repositories/account_repository.py
- app/database/importers/account_importer.py
- app/database/importers/player_importer.py
- app/database/importers/inventory_importer.py
- app/database/importers/base_importer.py
- app/database/importers/import_validator.py
- app/database/importers/import_data.py
- app/database/importers/import_report.py
- migrations/legacy_players.py
- migrations/versions/93510e8bf194_initial_database_schema.py
- requirements.txt
- pwdlib/_hash.py
- pwdlib/hashers/argon2.py
- docs/engineering/reviews/RO-038-security.md

`docs/engineering/reviews/RO-038-security.md` was opened only as a report-format example. It is not evidence of the current code. `app/database/importers/game_data_importer.py` was not opened. `migrations/env.py` was not opened. The live environment file and the live database were not opened.

## Findings

No critical findings. No high findings.

### Medium — missing account skips password verification

**Confirmed fact.** `app/services/account_service.py` `login` loads the account and then evaluates `account is None or not verify_password(password, account.password_hash)`. When the account is missing, `verify_password` is not called. An unknown username, a wrong password, and a non-active account all raise `AppError(401, "Invalid username or password")`.

**Confirmed fact.** `app/services/operator_service.py` `login` uses the same short-circuit: `operator is None or not verify_password(...) or operator.status != "active"`, then the same 401 detail.

**Interpretation.** The response body matches for those failures. The missing-user path does less work, so timing can still distinguish an unknown username.

### Medium — operator login has no failure limit

**Confirmed fact.** `app/services/auth_service.py` keeps an in-memory map and treats a host as limited at 5 failures inside 60 seconds. `login_player` checks that limit before calling `AccountService.login`, and records a failure when that call raises `AppError`.

**Confirmed fact.** `app/api/v1/auth.py` `POST /auth/login` calls `login_player`. `app/api/v1/admin_access.py` `POST /admin/auth/login` calls `OperatorService.login` directly. The operator method that was read does not consult the failure map.

**Interpretation.** Player HTTP login has the required in-memory limit. Operator password guessing on that admin route does not.

### Medium — token failures use a different 401 detail for an inactive account

**Confirmed fact.** `app/services/account_service.py` `account_for_token` raises `AppError(401, "Player unavailable")` when the account is missing or `status` is not `active`. A missing session, a revoked session, or an expired session raises `AppError(401, "Invalid or expired token")`.

**Confirmed fact.** `app/api/dependencies.py` `current_player` raises `AppError(401, "Player unavailable")` when the player row is missing or not active. `app/services/operator_service.py` `actor_for_token` raises `AppError(401, "Operator unavailable")` when the operator is missing or not active, and `AppError(401, "Invalid or expired token")` for a bad session.

**Interpretation.** Login uses one detail for bad credentials and inactive accounts. Token use tells those cases apart. A bearer that still decodes can reveal that the subject is missing or inactive.

## Controls present

**Confirmed fact.** `app/models/account.py` stores `password_hash` as a non-null `String(255)` and limits `status` with a check constraint to `active`, `suspended`, and `closed`. `AccountSession.token_hash` is a non-null unique `String(64)`. `revoked_at` is nullable.

**Confirmed fact.** `app/core/security.py` hashes passwords with `PasswordHash.recommended()` and hashes tokens with `hashlib.sha256(...).hexdigest()`. `requirements.txt` depends on `pwdlib[argon2]`. Installed `pwdlib/_hash.py` `PasswordHash.recommended` builds `Argon2Hasher`. Installed `pwdlib/hashers/argon2.py` defaults that hasher to Argon2id. A local inspection printed the hasher class name only. `app/core/config.py` requires `jwt_secret` and defaults `jwt_algorithm` to `HS256`. The live secret was not read.

**Confirmed fact.** `app/services/account_service.py` `register` assigns `password_hash=hash_password(password)`. `login` stores `token_hash=hash_token(token)` and returns the raw bearer once in `TokenResponse`. `account_for_token` rejects a non-active account, a missing hash row, a different `account_id`, a non-null `revoked_at`, and an `expires_at` in the past. `revoke_token` sets `revoked_at`.

**Confirmed fact.** `app/api/dependencies.py` `current_account` calls `account_for_token`. `app/networking/websocket.py` `_identity_for_token` calls the same method and treats `AppError` as authentication failure.

**Confirmed fact.** `app/repositories/account_repository.py` `session_by_hash` looks up `AccountSession.token_hash`.

**Confirmed fact.** `app/database/importers/account_importer.py` skips a username that `by_username` already finds, then calls `AccountService.register` with the source password. It does not assign a password column itself. `app/database/importers/player_importer.py` does not read or write a password. `app/database/importers/inventory_importer.py` calls `InventoryService.add_item`. The `add_item` method in `app/services/inventory_service.py` increases item quantity. The importers that were opened do not call `apply_currency` and do not assign a currency balance. `app/database/importers/import_data.py` rolls back when the report has errors or the run is a dry run. `app/database/importers/import_report.py` records created names, skipped names, and error strings.

**Confirmed fact.** `app/services/operator_service.py` `players`, `operators`, `set_player_status`, and `set_operator_status` return dictionaries with identity and status fields. `app/api/v1/admin_access.py` `create_operator` returns `id` and `username`. `me` returns id, username, status, roles, and permissions. Those methods do not put `password_hash` or `token_hash` in the returned dictionaries. `ensure_bootstrap` returns before creating an operator when the username or password setting is empty.

## Response schemas

**Confirmed fact.** Response schemas omit `password_hash` and `token_hash`.

A search of `app/schemas/` found neither field. The schema files opened were:

- `app/schemas/account.py`: `AccountResponse` has id, username, email, status, is_verified, created_at, updated_at, and last_login_at. `AccountSessionResponse` has id, account_id, expires_at, revoked_at, and created_at. `LoginHistoryResponse` has id, account_id, login_status, ip_address, and created_at. `AccountCreate` is a request model and accepts `password`.
- `app/schemas/auth.py`: `TokenResponse` has access_token, token_type, and expires_in. That access_token is the bearer returned to the client. It is not the stored `token_hash`. `PlayerCreated` has id and username. `RegisterRequest` and `LoginRequest` are request models and accept `password`.
- `app/schemas/player.py`: `PlayerProfile`, `PlayerResponse`, `PlayerStatisticsResponse`, and `PlayerUpdate`.
- `app/schemas/common.py`: `Page`.
- `app/schemas/inventory.py`: `InventoryItemResponse`, `InventoryResponse`, `CurrencyResponse`, `CurrencyChange`, and `ItemQuantityChange`.
- `app/schemas/cosmetics.py`: `WalletResponse` and `SkinResponse`.
- `app/schemas/configuration.py`: `ConfigurationResponse`, `FeatureResponse`, and `ConfigurationUpdate`.
- `app/schemas/game_data.py`: `DefinitionResponse`, `ItemDefinitionResponse`, `GameModeResponse`, and `MapDefinitionResponse`.
- `app/schemas/lobby.py`: lobby and team response models, plus `ReadyUpdate`, `LobbyCreate`, and `TeamCreate`.
- `app/schemas/match.py`: match summary, record, and result models.
- `app/schemas/maps.py`: map summary, version, detail, asset, and manifest models. `sha256` on those models is a file digest field. It is not `token_hash`.
- `app/schemas/__init__.py`: package marker only.

`app/api/v1/admin_access.py` `OperatorCreate` is a request model and accepts `password`. The admin response dictionaries read above omit both hash fields. `app/api/v1/admin_support.py` request models that were opened do not contain either hash field.

## Legacy upgrade

**Confirmed fact.** The legacy upgrade does not drop `legacy_players`.

The revision file is `migrations/versions/93510e8bf194_initial_database_schema.py`. Its `upgrade` calls `preserve_legacy_players` and then `copy_legacy_players`. It contains no drop of `legacy_players`.

`migrations/legacy_players.py` `preserve_legacy_players` renames an old `players` table to `legacy_players` when that table has `password_hash` and does not have `account_id`. `copy_legacy_players` reads `legacy_players` and inserts accounts, players, and player statistics. It skips an account id that already exists. It does not delete the legacy table. The copied `password_hash` value is the stored column value. This review did not open live rows, so the algorithm of those copied values was not confirmed.

`downgrade` in the same revision drops the new tables, including `players` and `accounts`, and then calls `restore_legacy_players`. That helper renames `legacy_players` back to `players` when `legacy_players` exists and `players` does not. A search of `migrations/` found no `drop_table` of `legacy_players`. The other revision files were not read line by line.

## Residual risk

The in-memory player limit is process-local, resets when the process restarts, and uses the immediate client host. That matches the control in `app/services/auth_service.py`. It does not cover operator login, which is the medium finding above.

Copied legacy password values were not re-hashed and were not compared with live data. A username collision during copy is not handled in `migrations/legacy_players.py`. Transaction rollback for a failed upgrade was not confirmed because `migrations/env.py` was not opened.

`downgrade` of `93510e8bf194` deletes the new account and player tables before restoring the legacy name. That path is destructive to rows created after the upgrade. The upgrade path keeps `legacy_players`.

`app/core/config.py` loads `jwt_secret` from the environment. This review did not open the environment file and did not record the secret. `import_data` prints the import report, which contains usernames and error strings. The report type does not include a password field. `game_data_importer.py` was not reviewed.

Original Rules of Survival authentication behavior remains unknown.

## Recommendation

Approve. Account storage, session hashes, response schemas, the account importer, and the legacy upgrade match the checks required for this review. The medium findings should be scheduled as follow-up. They do not show password or token hashes in response schemas, plaintext passwords written by the importer, or a drop of `legacy_players` on upgrade.

RECOMMENDATION: approve

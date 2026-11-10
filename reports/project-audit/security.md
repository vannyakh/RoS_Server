TASK ID: project-audit (does not close RO-009)
AGENT: security-engineer
PHASE: read-only security audit
STATUS: report written

IMPLEMENTATION: No application code, migrations, or environment files were modified.
FILES CREATED: reports/project-audit/security.md
FILES MODIFIED: none
DISCOVERIES: See findings below. RO-009 remains ready and has no security review report.
DATABASE CHANGES: none
API CHANGES: none
GAME FUNCTION CHANGES: none
TESTS EXECUTED: git check-ignore and git ls-files for ignore coverage; file existence check for the RO-009 review path. No authentication test suite was run.
TEST RESULTS: `.env` and `*.db` are ignored and are not tracked. `.env.example` and `docker-compose.yml` are tracked. `docs/engineering/reviews/RO-009-security.md` is absent.
COMPATIBILITY EVIDENCE: not applicable
KNOWN ISSUES: No logout route. Stored session hashes and `revoked_at` are not consulted when a token is accepted. RO-009 is still ready.
RECOMMENDATION: return

OBJECTIVE: Review secret handling, password hashing, token storage, git ignore rules for `.env` and database files, and whether a logout route exists.
IMPLEMENTATION SUMMARY: Read-only review of the files listed in the scope, plus the account model, auth routes, response schemas, settings, importer, and legacy migration needed to support those claims.
SECURITY CONSIDERATIONS: Findings are labeled Confirmed fact, Interpretation, or Unknown. No secret values are included.
DEPENDENCIES: RO-009 is ready, not completed. Its allowed report path was not written by this audit.

# Security audit

Reviewer: security-engineer. Scope was read-only. This file is the project audit. It is not `docs/engineering/reviews/RO-009-security.md`, and it does not change RO-009.

Evidence labels:

- **Confirmed fact** — read in a file, or observed from `git check-ignore` / `git ls-files`.
- **Interpretation** — conclusion drawn from those facts.
- **Unknown** — not established by a file that was opened.

## RO-009

**Confirmed fact.** In `.cursor/management/tasks.json`, RO-009 "Database security review" has `status` `ready`, `assigned_agent` `security-engineer`, `completed_at` null, and `completion_report` null. `files_allowed` is only `docs/engineering/reviews/RO-009-security.md`. The history note says no security report has been written.

**Confirmed fact.** That review path is not in the tree. The only file under `docs/engineering/reviews/` found by search is `RO-028-compatibility.md`.

**Confirmed fact.** RO-011 `block_reason` is "RO-009 is still ready and has no security review report."

**Interpretation.** This audit does not satisfy RO-009. The CTO still has to assign that review and record a file-cited report at the path in `files_allowed`.

## Findings

### High — issued tokens are not revoked

**Confirmed fact.** `app/api/v1/auth.py` registers `POST /auth/register` and `POST /auth/login` only. `app/api/router.py` mounts that router at `/api/v1` and does not add another auth router. A search of `app/api` found no logout route.

**Confirmed fact.** `app/services/account_service.py` `login` stores `token_hash=hash_token(token)` on `AccountSession` and returns the raw token in `TokenResponse`. `app/models/account.py` has `AccountSession.revoked_at`. Nothing under `app/` assigns `revoked_at`.

**Confirmed fact.** `app/api/dependencies.py` `current_account` calls `decode_access_token`, reads `sub`, loads the account, and rejects a missing account or a status other than `active`. It does not load `AccountSession` or compare `token_hash`. `app/networking/websocket.py` `_player_id_for_token` does the same: decode the JWT, load `Account` by `sub`, and require `status == "active"`.

**Interpretation.** A bearer token stays valid until it expires or the account is no longer `active`. Writing a session row does not create a revocation check. Logout cannot be done by deleting or stamping that row until the request path reads it.

### Medium — password check is skipped when the username is missing

**Confirmed fact.** `AccountService.login` uses `if account is None or not verify_password(...)` and then raises the same `AppError(401, "Invalid username or password")` for a missing account, a bad password, and a non-active account.

**Interpretation.** The message does not reveal which case failed. The `or` short-circuit skips the hash verify when the account is missing, so timing can still differ between an unknown username and a known one. That difference was not measured.

### Medium — login limiting is process-local

**Confirmed fact.** `app/services/auth_service.py` keeps failures in a module dict, allows 5 failures per 60 seconds per host, and uses `request.client.host` from `app/api/v1/auth.py` (or `"unknown"` when `request.client` is missing).

**Interpretation.** Another process or worker has its own counter. The host is whatever the ASGI server puts on `request.client`, which was not checked against a trusted-proxy setting.

### Medium — Compose database password is a committed placeholder, and Redis has no password

**Confirmed fact.** `docker-compose.yml` loads `env_file: .env`, overrides `DATABASE_URL` and `REDIS_URL`, sets `POSTGRES_USER` and `POSTGRES_PASSWORD` for the `postgres` service, and publishes only `8000:8000` for `game-server`. Redis is started as `redis-server --appendonly yes` with no authentication flag. Postgres and Redis use named volumes and have no published host ports.

**Interpretation.** The database password in that file is a placeholder, not a generated secret. Anyone who starts Compose without changing it shares that password on the Compose network. Redis on that network accepts commands without a password. The lack of published database ports limits exposure to hosts that can reach the containers.

### Low — ignore rules cover `.env` and `*.db` only

**Confirmed fact.** `.gitignore` lists `.env` and `*.db`. `git check-ignore` attributes `.env`, `ros_server.db`, and `app.db` to those rules. `git ls-files` does not track `.env` or `ros_server.db`. It does track `.env.example` and `docker-compose.yml`. `git check-ignore` does not ignore `data.sqlite` or `data.sqlite3`.

**Interpretation.** The configured SQLite name in settings ends in `.db`, so that filename is ignored. A database file that does not use the `.db` suffix would not match this rule. `.env.example` is meant to be committed; it is not a live secret file.

## Controls that were present

**Confirmed fact.** `app/core/security.py` hashes passwords with `pwdlib.PasswordHash.recommended()` and hashes tokens with `hashlib.sha256(...).hexdigest()`. `requirements.txt` depends on `pwdlib[argon2]`. `create_access_token` puts `sub`, `exp`, and `iat` in the JWT and signs with `settings.jwt_secret` and `settings.jwt_algorithm`. `decode_access_token` verifies with `algorithms=[settings.jwt_algorithm]`.

**Unknown.** The installed `pwdlib` package was not in the workspace virtualenv search, so the Argon2 variant, memory cost, time cost, and parallelism were not read from library source. The application code does not name those parameters.

**Confirmed fact.** `app/core/config.py` declares `jwt_secret: str` with no default and loads `env_file=".env"`. Defaults in that file are `jwt_algorithm` `HS256` and `jwt_expire_minutes` `60`.

**Confirmed fact.** `app/schemas/account.py` `AccountResponse` and `AccountSessionResponse` have no `password_hash` or `token_hash` fields. `AccountSessionResponse` does include `expires_at` and `revoked_at`. A search of `app/schemas` found no `password_hash` or `token_hash` fields. `app/schemas/auth.py` `TokenResponse` returns `access_token`, `token_type`, and `expires_in`. `RegisterRequest` requires a password length of 12 to 128. `LoginRequest` allows a password length of 1 to 128.

**Confirmed fact.** `app/database/importers/account_importer.py` skips a username that already exists and calls `AccountService.register` with the import record's password. `register` stores `hash_password(password)` and does not assign the plaintext password onto the account.

**Confirmed fact.** `migrations/legacy_players.py` renames an old `players` table to `legacy_players` when it has `password_hash` and no `account_id`, then copies `password_hash` into `accounts`. `upgrade()` in `migrations/versions/93510e8bf194_initial_database_schema.py` calls `preserve_legacy_players` and `copy_legacy_players`. A search of that revision shows `drop_table` only in `downgrade()`. `downgrade()` drops the new tables and then calls `restore_legacy_players`, which renames `legacy_players` back to `players` when `players` is absent.

**Interpretation.** Upgrade does not drop `legacy_players`. Downgrade of a database that still has the new `players` table would drop that new table and would leave `legacy_players` in place only when the rename condition is not met. That downgrade path was read, not executed.

## Residual risk

Logout and session revocation are unimplemented on both HTTP and WebSocket. Account status still blocks a suspended or closed account. Token lifetime follows `jwt_expire_minutes` (default 60). The live `.env` value was not opened. Argon2 parameters were not confirmed from the installed library. Whether a proxy sits in front of `request.client.host` was not checked. RO-009 remains ready until a review is written to `docs/engineering/reviews/RO-009-security.md` and the CTO records it.

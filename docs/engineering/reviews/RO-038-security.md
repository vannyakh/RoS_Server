TASK ID: RO-038
AGENT: security-engineer
PHASE: read-only authentication lifecycle review
STATUS: report written

IMPLEMENTATION: No application code, tests, migrations, environment files, or task registry files were modified.
FILES CREATED: docs/engineering/reviews/RO-038-security.md
FILES MODIFIED: none
DISCOVERIES: Login inserts an AccountSession with a SHA-256 token hash and commits before the raw token is returned. HTTP and WebSocket authentication do not read token_hash, expires_at, or revoked_at. No logout path exists. decode_access_token rejects an expired JWT.
DATABASE CHANGES: none
API CHANGES: none
GAME FUNCTION CHANGES: none
TESTS EXECUTED: No pytest run. Installed PyJWT 2.15.1 default options and the pwdlib recommended hasher class were inspected. No secret and no password hash was printed.
TEST RESULTS: not run
COMPATIBILITY EVIDENCE: not applicable. Original Rules of Survival logout behavior is unknown. This review does not mark any feature compatible.
KNOWN ISSUES: A bearer token stays usable until the JWT expires or the account status is not active. The stored session row cannot revoke it.
RECOMMENDATION: approve

OBJECTIVE: Decide whether logout plus AccountSession checks can be implemented without a new protocol, without weakening Argon2 or JWT checks, and without rejecting sessions that are still valid.
IMPLEMENTATION SUMMARY: Read-only review of the account model, login insert, auth service, token helpers, HTTP current_account, the auth router, WebSocket token lookup, and the account repository.
SECURITY CONSIDERATIONS: Findings cite files that were opened. No JWT secret, raw token, or password hash is included. Severity labels are critical, high, and medium. No critical finding.
DEPENDENCIES: This report does not change task status. Logout still has to be implemented and reviewed again against the conditions below.

# RO-038 authentication lifecycle

Reviewer: security-engineer. Scope was read-only.

## Findings

### High — session rows are written and never enforced

**Confirmed fact.** `app/services/account_service.py` `login` inserts `AccountSession` with `token_hash=hash_token(token)` and `expires_at`. It does not set `revoked_at`.

**Confirmed fact.** `app/api/dependencies.py` `current_account` calls `decode_access_token`, reads `sub`, loads `Account` with `AccountRepository.by_id`, and rejects a missing account or a status other than `active`. It does not load `AccountSession`.

**Confirmed fact.** `app/networking/websocket.py` `_player_id_for_token` calls `decode_access_token`, loads `Account` with `session.get`, and rejects a missing account or a status other than `active`. It does not load `AccountSession`.

**Confirmed fact.** `app/api/v1/auth.py` registers `POST /auth/register` and `POST /auth/login` only. `app/services/auth_service.py` exposes `register_player` and `login_player` only. `app/repositories/account_repository.py` queries `Account` and `LoginHistory` only. A search of `app/` found no assignment to `revoked_at` and no logout route or method.

**Interpretation.** Logout cannot take effect until both HTTP and WebSocket look up the stored hash. A check on only one of those paths leaves the other path accepting a revoked bearer until the JWT expires.

## Answers

### 1. When a session row is created, and what is stored

**Confirmed fact.** The row is created only on the success path of `AccountService.login` in `app/services/account_service.py`, after the password verifies and `account.status == "active"`. Failed logins write `LoginHistory` and do not insert `AccountSession`.

**Confirmed fact.** The inserted columns are `account_id=account.id`, `token_hash=hash_token(token)`, and `expires_at=now + timedelta(minutes=settings.jwt_expire_minutes)`. `revoked_at` is omitted, so it stays null. `app/models/account.py` defines `token_hash` as `String(64)`, unique and non-null, `expires_at` as non-null, and `revoked_at` as nullable.

**Confirmed fact.** `app/core/security.py` `hash_token` returns `hashlib.sha256(token.encode("utf-8")).hexdigest()`. The raw token is returned once in `TokenResponse(access_token=token, expires_in=token_expires_in())`. It is not a column on `AccountSession`.

### 2. Whether HTTP auth checks token_hash, expires_at, and revoked_at

**Confirmed fact.** No. `app/api/dependencies.py` `current_account` does not read those columns. It accepts the request when `decode_access_token` succeeds, `sub` is present, and the account exists with `status == "active"`.

The JWT `exp` claim is a separate check inside `decode_access_token`. It is not a read of `account_sessions.expires_at`.

### 3. Whether WebSocket auth checks those columns

**Confirmed fact.** No. `app/networking/websocket.py` `_player_id_for_token` does not read `token_hash`, `expires_at`, or `revoked_at`. It accepts the socket when `decode_access_token` succeeds, `sub` is present, and the account exists with `status == "active"`. A decode failure returns `None`, and `_authenticate` closes with code 4003.

`app/networking/protocol.py` allows message type `auth` and has no logout type. That file was read to bound the protocol. WebSocket authentication stays on the existing `auth` payload token.

### 4. Whether logout exists

**Confirmed fact.** No. `app/api/v1/auth.py` has register and login only. `app/api/router.py` mounts that router at `/api/v1` and does not add another auth router. `app/services/auth_service.py` and `app/services/account_service.py` have no logout or revoke method. `app/models/account.py` has `revoked_at`, and nothing under `app/` assigns it.

### 5. Transaction boundary of login

**Confirmed fact.** `AccountService.login` in `app/services/account_service.py` is the commit boundary. The route and `login_player` do not commit. `app/infrastructure/database.py` `get_db` yields a session and does not commit.

On a bad password, an unknown username, or a non-active account, `login` commits the failure history and then raises. On success it updates `last_login_at`, adds the `AccountSession`, records success history, `await self.session.commit()`, and only then returns `TokenResponse`. The client does not receive the raw token until that commit has returned.

### 6. Whether an expired JWT is rejected by decode_access_token

**Confirmed fact.** Yes, by the application call and the installed library default. `app/core/security.py` `decode_access_token` calls `jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])` and maps every `jwt.PyJWTError` to `AppError(401, "Invalid or expired token")`. The call does not pass `options` and does not disable expiration checks.

**Confirmed fact.** Installed PyJWT 2.15.1 `jwt/api_jwt.py` `_get_default_options` sets `verify_exp` to `True`. `ExpiredSignatureError` subclasses `InvalidTokenError` and `PyJWTError`, so it is caught by `decode_access_token`. `tests/compatibility/authentication/test_login.py` `test_expired_token_is_rejected` expects that 401. This review did not re-run that test, because the test signs with the configured secret.

`app/core/config.py` defaults `jwt_algorithm` to `HS256` and `jwt_expire_minutes` to 60. The live `.env` value was not opened.

### 7. Recommendation

Approve implementation of logout plus session-row checks on both HTTP and WebSocket.

Current rows can keep working. Login already stores the SHA-256 hash, sets `expires_at`, leaves `revoked_at` null, and commits before the token is returned. A lookup of that hash accepts an unexpired, unrevoked session. `create_access_token` is called with `account.id`, and `AccountSession.account_id` is that same id.

## Controls that must stay

**Confirmed fact.** `app/core/security.py` hashes passwords with `PasswordHash.recommended()`. The installed pwdlib object uses `Argon2Hasher`. `verify_password` uses that same object. Tokens are SHA-256 hex digests, not raw token columns.

**Confirmed fact.** `app/schemas/auth.py` `TokenResponse` returns `access_token`, `token_type`, and `expires_in`. `app/schemas/account.py` `AccountResponse` and `AccountSessionResponse` have no `password_hash` or `token_hash` fields. `AccountSessionResponse` includes `expires_at` and `revoked_at`. No route in the files read returns `AccountSessionResponse`.

**Confirmed fact.** HTTP and WebSocket both reject an account whose status is not `active`, after the JWT decode. `app/models/account.py` limits status to `active`, `suspended`, and `closed`.

## Approval conditions

The implementation this review approves is limited to the following:

- Logout is an HTTP route on the existing `/api/v1/auth` router, using the existing bearer token. Do not add a WebSocket message type. `ClientMessage` in `app/networking/protocol.py` stays as it is.
- Revoke only the presented session by setting `revoked_at` on the row whose `token_hash` equals `hash_token` of that bearer. Do not store or return the raw token or the hash. Other unexpired, unrevoked sessions stay valid.
- After a successful `decode_access_token`, both `current_account` and `_player_id_for_token` load that session. Reject a missing row, a non-null `revoked_at`, or an `expires_at` in the past. Keep the `status == "active"` check.
- Query `AccountSession` directly. `app/models/account.py` sets `Account.sessions` to `lazy="raise"`, so touching the relationship will fail the request.
- Match `account_id` to the JWT `sub`. Login puts `account.id` in that claim. Do not look the session up by a player id.
- Commit the revocation in the service, as `login` commits the insert. `get_db` does not commit.
- Do not change `PasswordHash.recommended()`, `hash_password`, `verify_password`, `hash_token`, or `jwt.decode`. Do not pass options that disable `verify_exp`, and do not widen `algorithms`.
- Response schemas continue to omit `password_hash` and `token_hash`.

## Residual risk

Until that implementation lands, a stolen bearer works on HTTP and WebSocket until `decode_access_token` rejects it or the account is no longer `active`. The code default lifetime is 60 minutes. The live setting was not read.

`app/services/auth_service.py` still counts login failures in a process-local dict, 5 failures per 60 seconds per host. That limiter is outside this approval.

Original client logout behavior remains unknown. This approval is for this server's bearer session row, not an official game packet.

A later review should return the change if it adds a socket message, weakens Argon2 or JWT verification, skips either HTTP or WebSocket, or rejects a session that is unexpired and unrevoked.

RECOMMENDATION: approve

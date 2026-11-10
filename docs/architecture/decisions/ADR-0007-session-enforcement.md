# ADR-0007 — Enforce stored sessions and separate readiness

- Decision ID: ADR-0007
- Date: 2026-11-10
- Status: accepted

## Context

Login already inserts an `AccountSession` row with a SHA-256 token hash and commits before the raw token is returned. HTTP and WebSocket authentication previously accepted any unexpired JWT for an active account. `GET /health` returns `{"status":"ok"}` and existing clients depend on that body.

## Problem

A stored session could not be revoked, and two logins in the same second produced the same token. Readiness also needs a database check that must not change the liveness response.

## Options considered

- Add a new WebSocket logout message and a new token format.
- Keep the bearer token, check the stored session on both HTTP and WebSocket, and add `GET /ready` beside the existing health response.

## Chosen solution

Logout is `POST /api/v1/auth/logout`. It sets `revoked_at` on the presented session only. After JWT decode, HTTP and WebSocket both load the session by its hash, match `account_id` to the token subject, and reject a missing, revoked, or expired row. New tokens include a unique `jti` so each login has its own hash. `jwt.decode` still verifies expiration. `GET /health` stays `{"status":"ok"}`. `GET /ready` runs `SELECT 1` and returns ready or HTTP 503 `not_ready`.

## Reason

The RO-038 review approved this boundary. It does not add a protocol message, weaken Argon2, or disable JWT expiration checks.

## Consequences

A revoked bearer is rejected on both HTTP and WebSocket. Other sessions for the same account stay valid. Original Rules of Survival logout and lobby behavior stay unknown. PostgreSQL execution is still a separate environment task.

## Related tasks

RO-038, RO-039, RO-043, RO-044

## Related changes

CH-0003, CH-0005

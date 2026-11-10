# ADR-0002 — Account identity and hashed session storage

- Decision ID: ADR-0002
- Date: 2026-11-10
- Status: accepted

## Context

Login and profile are separate rows. Sessions are stored on the server.

## Problem

Responses must not reveal password or token secrets.

## Options considered

- Store plaintext tokens.
- Store Argon2 password hashes and SHA-256 session token hashes.

## Chosen solution

`accounts` is the login row and the JWT subject. `players` is one profile per account. Passwords use Argon2. Session tokens are stored as SHA-256 hashes and omitted from response schemas.

## Reason

This is the recorded identity decision.

## Consequences

A future logout path has to revoke the stored hash. RO-009 still reviews the implementation.

## Related tasks

RO-003, RO-006, RO-009

## Related changes

None.

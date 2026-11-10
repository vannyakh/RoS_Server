# ADR-0003 — UUID keys and portable JSON

- Decision ID: ADR-0003
- Date: 2026-11-10
- Status: accepted

## Context

Development uses SQLite. The production layout expects PostgreSQL.

## Problem

One Alembic revision has to serve both databases.

## Options considered

- Use database-specific key types.
- Use UUID string keys and portable JSON.

## Chosen solution

Primary keys are UUID strings. JSON columns use `PortableJSON`. The Python attribute is `details`. Relationships use `lazy="raise"`.

## Reason

This is the recorded portability decision.

## Consequences

A skipped PostgreSQL test is not a production verification. A new key style needs a new decision.

## Related tasks

RO-003, RO-004

## Related changes

None.

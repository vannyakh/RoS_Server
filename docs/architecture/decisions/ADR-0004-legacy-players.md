# ADR-0004 — Preserve legacy player rows

- Decision ID: ADR-0004
- Date: 2026-11-10
- Status: accepted

## Context

An older `players` table existed before the normalized schema.

## Problem

Upgrade must not destroy those rows.

## Options considered

- Drop the old table during upgrade.
- Rename it to `legacy_players` and copy rows.

## Chosen solution

Revision `93510e8bf194` renames `players` to `legacy_players`, creates the new tables, and copies rows. Upgrade does not drop the legacy table. Downgrade is for a disposable database.

## Reason

Player-owned rows are protected.

## Consequences

Do not rewrite this applied revision. Do not delete `legacy_players`.

## Related tasks

RO-004, RO-009

## Related changes

None.

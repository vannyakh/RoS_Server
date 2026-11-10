# ADR-0008 — Stored match records stay separate from the live match

- Decision ID: ADR-0008
- Date: 2026-11-10
- Status: accepted

## Context

`GET /api/v1/matches` reads the in-memory matchmaker. `MatchService` stores scheduled, lobby, running, completed, and cancelled rows. Those two identifiers are not the same.

## Problem

Putting stored lifecycle routes on `/matches/{id}` would let a durable id and a live id share one path.

## Options considered

- Overload `/api/v1/matches` with stored create, cancel, and finalize.
- Keep live snapshots on `/matches` and stored lifecycle on `/match-records`.

## Chosen solution

`/api/v1/match-records` creates a stored match, adds the authenticated player, changes status, and finalizes results. Cancel is a participant-only transition to `cancelled`. Completion is `POST /results`, not a status string. `/api/v1/matches` remains the live list.

## Reason

The live loop does not write SQL every tick. The stored row is the durable lifecycle. Mixing the ids would make cancel and finalize apply to the wrong match.

## Consequences

A stored cancel does not stop an in-memory match. Experience and equipment rewards are still not granted. Original matchmaking behavior stays unknown.

## Related tasks

RO-048

## Related changes

CH-0006

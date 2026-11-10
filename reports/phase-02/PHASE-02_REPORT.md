# Phase 02 — Core game services

Checkpoint: CP-0004 / PHASE-02-CORE-SERVICES

HEAD remains `6b7c55cc6a1659169292ce123a8105814b2d13df`. This phase was not committed and was not pushed.

Account registration, login, logout, and the player profile were already in place. Lobby create, join, leave, ready, team create, and team join were already in place. This phase adds the missing stored operations: inventory, team leave, and match-record lifecycle.

No specialist subagent was launched. The CTO wrote the routes and ran the tests. Original Rules of Survival compatibility stays **0 compatible, 43 unknown**.

## Completed

| Task | Result |
| --- | --- |
| RO-046 | `GET /api/v1/inventory`, add, remove, and currency for the authenticated player |
| RO-047 | `DELETE /api/v1/lobby/teams/{team_id}/members` leaves the team and keeps the lobby membership |
| RO-048 | `POST /api/v1/match-records` creates, joins, cancels, and finalizes a stored match |
| RO-049 | `tests/integration/test_core_services.py` |

`python -m pytest -q --tb=line` returned **75 passed, 1 skipped**, 69.77s. The previous suite was 72 passed, 1 skipped. The skip is still the PostgreSQL roundtrip. The focused core-service run was 10 passed.

## Left open

- Experience and progression rewards. No original values exist, so none were invented. RO-018 stays backlog.
- Equipment is still not equipped by the match loop.
- A stored cancel does not stop an in-memory match. `GET /api/v1/matches` is unchanged.
- RO-009 is ready, RO-011 and RO-045 are blocked, and RO-035 stays in review.
- RO-019 still covers lobby gaps other than leave, ready, and team leave.

## Records

ADR-0008 separates `/match-records` from the live match list. Changelog row CH-0006. No migration was added. Head remains `93510e8bf194`.

Validators: `OK: 13 agents, 49 tasks` and `OK: 49 tasks, 10 discoveries, 43 compatibility features`.

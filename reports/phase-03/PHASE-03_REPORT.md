# Phase 03 — Gameplay simulation

Checkpoint: CP-0005 / PHASE-03-GAMEPLAY

HEAD remains `6b7c55cc6a1659169292ce123a8105814b2d13df`. This phase was not committed and was not pushed.

World state, on-foot movement, player state, combat, weapons, and match results were already covered by the in-memory simulator. This phase adds a local vehicle and records the match clock and result fields.

No specialist subagent was launched. Original compatibility stays **0 compatible, 43 unknown**.

## Completed

| Task | Result |
| --- | --- |
| RO-050 | A buggy uses speed 12 only while boarded. On-foot speed stays 5. Shooting is rejected in the vehicle. |
| RO-051 | Countdown follows `MatchRules.countdown`. Results record placement and kills, and have no experience field. |

`python -m pytest -q --tb=line` returned **80 passed, 1 skipped**, 67.87s. The previous suite was 75 passed, 1 skipped. The skip is still the PostgreSQL roundtrip. The focused simulation run was 14 passed.

## Left open

- Equipment is still not equipped by the match loop.
- Experience and currency rewards were not added. No original values exist.
- RO-009 is ready. RO-011 and RO-045 are blocked. RO-035 stays in review.
- RO-029, RO-030, and RO-031 stay backlog because they still depend on the research tasks.

## Records

ADR-0009 records the vehicle split. Changelog row CH-0007. No migration was added. Head remains `93510e8bf194`.

Validators: `OK: 13 agents, 51 tasks` and `OK: 51 tasks, 10 discoveries, 43 compatibility features`.

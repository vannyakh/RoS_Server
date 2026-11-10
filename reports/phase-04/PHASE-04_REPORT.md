# Phase 04 — Client compatibility research

Checkpoint: CP-0006 / PHASE-04-CLIENT-RESEARCH

HEAD remains `6b7c55cc6a1659169292ce123a8105814b2d13df`. This phase was not committed and was not pushed.

No client binary was downloaded. No unofficial packet field was copied. Original compatibility stays **0 compatible, 43 unknown**.

## What was recorded

RO-013, RO-014, and RO-015 now separate observed facts from hypotheses. The network page lists this server's message types and actions. `tests/compatibility/protocol/test_contract.py` checks that list against `app/networking/protocol.py`.

A public search on 2026-11-10 returned shutdown notices and one unofficial forum thread. DIS-0011 records that search. The forum thread is not an authorized interface. Nothing from it was implemented.

## Tests

The contract module plus the existing protocol tests: 8 passed in 0.19s.

`python -m pytest -q --tb=line` returned **82 passed, 1 skipped**, 64.40s. The skip is the PostgreSQL roundtrip.

## Still unknown

Original account, combat, vehicle, reward, and packet behavior. RO-033 stays backlog until an authorized reference and a comparison exist.

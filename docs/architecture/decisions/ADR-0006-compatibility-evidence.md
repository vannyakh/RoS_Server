# ADR-0006 — Local tests do not prove original compatibility

- Decision ID: ADR-0006
- Date: 2026-11-10
- Status: accepted

## Context

RO-020 recorded 43 server functions. RO-028 reviewed the matrix and the suite.

## Problem

A passing test of this server can be mistaken for original Rules of Survival behavior.

## Options considered

- Treat a passing local test as compatible.
- Keep implementation status, test status, and original compatibility as separate fields.

## Chosen solution

`compatibility_status` stays `unknown` unless an authorized original reference is cited and a comparison passed. Research records separate observed fact, interpretation, hypothesis, and implementation impact.

## Reason

DIS-0001: no authorized original specification is in this repository.

## Consequences

Do not mark a feature compatible from app tests alone. Do not invent weapon stats, maps, or packet formats. A hypothesis is not promoted without new evidence.

## Related tasks

RO-020, RO-028

## Related changes

CH-0001

# ADR-0001 — Modular monolith and local JSON protocol

- Decision ID: ADR-0001
- Date: 2026-11-10
- Status: accepted

## Context

The server is a Python 3.12 FastAPI application. HTTP and WebSocket code call services. Services call repositories. The 20 Hz match loop keeps positions in memory.

## Problem

The reconstruction needs one process shape and a wire format that is not mistaken for an official client protocol.

## Options considered

- Split the services into separate deployable processes now.
- Keep a modular monolith and a project-specific JSON protocol.

## Chosen solution

Keep the modular monolith and this project's JSON protocol.

## Reason

This is the decision already recorded in `docs/engineering/ARCHITECTURE_DECISIONS.md`.

## Consequences

Official packet formats stay out of scope. A process split or a protocol change needs a new decision record.

## Related tasks

RO-001, RO-002

## Related changes

None.

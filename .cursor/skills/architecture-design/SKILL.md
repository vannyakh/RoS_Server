---
name: architecture-design
description: Reviews RoS_Server module boundaries across API, services, repositories, models, game, and networking. Use when deciding where a feature belongs or when an import crosses layers.
---

# Architecture design

## When

A change touches more than one of `app/api`, `app/services`, `app/repositories`, or `app/game`.

## Input

The task id, the proposed files, and the current import direction.

## Workflow

1. Place request and response types in `app/schemas/`.
2. Place queries in `app/repositories/` and rules in `app/services/`.
3. Keep `app/game/simulate.py` free of SQLAlchemy imports.
4. Keep the custom JSON protocol in `app/networking/protocol.py`. Do not add an official-protocol adapter.
5. If the design needs a new table, hand that part to the database engineer instead of editing models from an API task.

## Checklist

- Layer direction preserved
- Tick path has no database call
- New module has one owning task
- Shared infrastructure file has one owner

## Output

A short boundary decision: owner module, allowed imports, and files that must not change.

## Failure

Stop when the only way forward is editing a file owned by another active task. Return the conflict to the CTO.

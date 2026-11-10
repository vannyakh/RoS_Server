---
name: project-onboarding
description: Inspects the RoS_Server repository and reports architecture, database status, and running processes. Use when starting a session, onboarding an agent, or before planning new work.
---

# Project onboarding

## When

A specialist is new to the checkout, or the CTO is about to plan work.

## Input

Repository root and, when present, `.cursor/management/tasks.json`.

## Workflow

1. Read `README.md`, `app/main.py`, `app/core/config.py`, and `app/infrastructure/database.py`.
2. List model modules under `app/models/` and the current Alembic revision in `migrations/versions/`.
3. Confirm the development URL is SQLite and production settings expect PostgreSQL.
4. Check `tasks.json` for `in_progress` tasks before editing.
5. Do not print values from `.env`.

## Conventions

The game tick does not query SQL. Account ids are the JWT subject. Official Rules of Survival packet formats are out of scope.

## Checklist

- Entry point and settings file identified
- Model modules and revision id recorded
- Active registry tasks recorded
- No secret values included

## Output

A one-page status note: architecture, revision, open tasks, and files the next task may edit.

## Failure

If `tasks.json` fails validation, stop and run `python scripts/validate_agent_registry.py`. Do not plan new tasks on an invalid registry.

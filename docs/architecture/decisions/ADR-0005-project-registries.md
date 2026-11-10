# ADR-0005 — Management registries are the project record

- Decision ID: ADR-0005
- Date: 2026-11-10
- Status: accepted

## Context

The reconstruction continues across Cursor sessions. A chat summary is not a durable record of research or implementation.

## Problem

The project needs permanent records of research, tasks, tests, compatibility, changes, and ownership.

## Options considered

- Treat conversation history as the project record.
- Keep JSON registries for tasks, discoveries, compatibility, checkpoints, milestones, decisions, and changelog.

## Chosen solution

`.cursor/management/*.json` is the source of truth. The CTO is the only role that changes task assignment or status. Checkpoint history and released changelog rows are append-only. Registry updates use a timestamped backup and an atomic replace.

## Reason

Another session should resume from files and command evidence.

## Consequences

A file existing on disk does not change a task's status. Specialists do not edit the registries. These JSON files are not the game database.

## Related tasks

RO-012

## Related changes

CH-0001

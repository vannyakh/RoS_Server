# ADR-0011 — Centralized admin backend and runtime boundary

- Decision ID: ADR-0011
- Date: 2026-11-11
- Status: accepted

## Context

The server is one FastAPI process. `app/main.py` starts `TickManager`, which steps the loop in `app/game` on that process. One Uvicorn worker owns the in-memory queue and the live matches. `game_runtime/session.py` constructs a `GameEngine` in-process for tests and the headless benchmark. The empty directories beside `game_runtime/README.md` are reserved names. Public HTTP lives under `/api/v1`. Map drafts live at `/api/v1/admin/maps` and accept an account only when its username is listed in `MAP_PUBLISHERS`. The sibling admin tree is documentation. Development storage is SQLite. PostgreSQL is the intended production database and is unverified. Redis in `app/infrastructure/redis.py` is an optional client. It holds no match state, and `GET /ready` does not call it. Compose files exist. `docs/operations/RELEASE_STATUS.md` and `docs/ARCHITECTURE.md` state that Compose is not a release and must not run against the live SQLite file.

## Problem

Administration, live-match control, and a future second process need a boundary before any admin routes or runtime packages are added. A second backend, a microservice per admin page, or empty `game_runtime` modules would look like a split the code does not have.

## Options considered

Deployment:

- Docker Compose on one machine first.
- Separate control and game hosts when load requires it.
- A k3s cluster, with Terraform and Ansible later.

Database:

- PostgreSQL plus Redis.
- SQLite plus Redis for development.
- PostgreSQL only.

Game runtime:

- A separate runtime process in this same repository.
- The loop stays inside the FastAPI process.
- A runtime deployed as its own service from the start.

## Chosen solution

The target is Docker Compose on one machine, PostgreSQL plus Redis, and a separate runtime process in this repository. Separate control and game hosts wait until load requires them. k3s, Terraform, and Ansible wait until after that host split. Until an implementation task changes the code, SQLite remains the verified development database, the loop still starts from `app/main.py`, and Redis stays optional.

This repository stays the only backend. FastAPI remains the control plane. Admin HTTP is a future module of that same application. There is no second admin backend and no microservice per feature. The React admin is a separate frontend (React, TypeScript, Vite, Tailwind, shadcn/ui) and is outside this change. The sibling admin tree stays documentation. This decision does not scaffold that frontend.

An admin handler sends a validated command. The runtime accepts or rejects the command and is the writer of live match memory. The handler does not write live match memory or player rows behind the simulation. That command channel is a design boundary. It is not implemented. No queue, socket, or `admin_commands` package exists for it.

## Reason

ADR-0001 keeps one modular monolith until a decision names a process split. ADR-0010 keeps the Python loop authoritative and leaves a separate process to a later decision. This record is that decision. Empty packages do not perform the split, and `app/game/simulate.py` stays on its current path.

## Current and target

| Choice | Today | Target |
| --- | --- | --- |
| Deployment | Compose files exist and are not a release. They must not run against the live SQLite file. This decision does not start Compose. | Docker Compose on one machine. Separate control and game hosts only when load requires it. k3s, Terraform, and Ansible come later. |
| Database | SQLite is the verified development database. PostgreSQL is intended and unverified. Redis is an optional client, holds no match state, and is outside `GET /ready`. `DATABASE_URL` is unchanged. | PostgreSQL plus Redis. Durable player rows stay in PostgreSQL. Redis is cache and temporary shared state. Live match state stays in the runtime. |
| Game runtime | The authoritative loop is in-process in `app/game`, started from `app/main.py`, with one Uvicorn worker. `game_runtime/session.py` calls that same engine in-process. | A separate runtime process in this repository. The split is recorded here and is not implemented. |

## Command boundary

A future admin route validates a command and hands it to the runtime. The runtime applies the change or rejects it. Player-row writes that affect a live match follow the same rule. Map publishing that exists today writes catalog and asset rows through `MapService` behind the `MAP_PUBLISHERS` username allow-list. That path is the current map publisher. It is not the live-match command channel, and it is not RBAC. RBAC does not exist.

## Consequences

Public `/api/v1` routes stay in place: auth, players, lobby, matches, match records, items, inventory, cosmetics, and maps. The cosmetics wallet stays at 500 coin and 20 diamond, with skins `recruit`, `field_jacket` at 200 coin, and `night_ops` at 15 diamond. The JSON protocol in `app/networking/protocol.py` stays the wire format. The original client remains NOT_SUPPORTED. This record names no original opcodes and no new admin message fields.

The page prefixes in `docs/ADMIN_ARCHITECTURE.md` are a future contract. When they are added, the prefix stays versioned and authenticated and does not replace the public `/api/v1` routes. Real-time admin views use the existing WebSocket at `/api/v1/ws` or a later server-sent-events channel. Repeated polling is outside this design. This change adds no socket.

Phases 1 through 6 on that page are a sequence. Phase 1 is admin authentication and RBAC. That work has not started.

This change adds no routes, no Python modules, and no migration. `app/game/simulate.py` is not moved. No Python files are added under the empty `game_runtime` directories.

## Related tasks

None. The CTO assigns any implementation task. This record does not change task status.

## Related changes

`docs/ADMIN_ARCHITECTURE.md`, `docs/ARCHITECTURE.md`, `docs/CUSTOM_SERVER_ARCHITECTURE.md`, `docs/engineering/ARCHITECTURE_DECISIONS.md`

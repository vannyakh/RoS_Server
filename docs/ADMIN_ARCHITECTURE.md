# Centralized admin backend

This page is the readable form of ADR-0011. It records the target shape and the code that exists today. It adds no routes, no Python modules, and no frontend.

The backend stays this repository. FastAPI remains the control plane. Admin features are future modules of that application. There is no second admin backend and no microservice per page. The React admin is a separate frontend and is not built here.

## Components

```text
React admin (separate frontend, documentation only today)
        |
        |  future versioned authenticated HTTP
        v
FastAPI control plane in this repository
  accounts, sessions, public /api/v1, future admin commands
        |
        |  in-process calls today
        |  a separate runtime process is the target
        v
Authoritative loop in app/game
        |
        |  finished totals only
        v
SQLite today, PostgreSQL intended
```

| Component | Target responsibility | What the code does today |
| --- | --- | --- |
| Admin web application | React, TypeScript, Vite, Tailwind, and shadcn/ui. Pages for dashboard, players, matches, maps, and configuration. | The sibling admin tree is documentation only. No console is built. |
| FastAPI control plane | Authenticated admin requests, validation, and routing inside this repository. | `app/api` serves the public `/api/v1` contract and `/api/v1/admin/maps`. |
| Authentication | Admin login, sessions, and access control. | Player auth is `/api/v1/auth`. Passwords are Argon2 hashes. Tokens are stored as SHA-256 hashes. RBAC does not exist. |
| Player service | Accounts, profiles, bans, and inventory inspection. | `/api/v1/players/me` and `/api/v1/inventory` act for the signed-in player. |
| Lobby service | Rooms, teams, and matchmaking views. | `/api/v1/lobby` is the player lobby API. The live queue is in `app/game`. |
| Match service | Match lifecycle and results. | `/api/v1/matches` is in-memory. `/api/v1/match-records` is the stored lifecycle. ADR-0008 keeps them separate. |
| Configuration service | Weapons, maps, rules, and settings. | Weapon numbers live in `app/game/items.py`. `MatchRules` lives in `app/game/rules.py`. |
| Game runtime | Authoritative sessions, movement, combat, inventory, zone, vehicles, and matches. | The loop is in-process in `app/game`, started from `app/main.py`. |
| Workers | Background jobs and scheduled tasks. | No worker package exists. |
| Database | Durable game and administration rows. | SQLite is the verified development database. PostgreSQL is intended and unverified. |
| Redis | Cache and temporary shared state. | Optional client in `app/infrastructure/redis.py`. It holds no match state and is outside `GET /ready`. |
| Monitoring | Metrics, health, logs, and alerts. | `GET /health`, `GET /ready`, and `GET /metrics` exist. Player ids are not metric labels. |
| Asset storage | Map bytes the client can download. | Metadata is in SQL. Bytes are under `storage/game_assets`. |

## Deployment

Compose files exist for a future isolated database. They are not a release, and they must not run against the live SQLite file. `docs/operations/RELEASE_STATUS.md` records that Compose was not started. This decision does not start Compose.

The target is Docker Compose on one machine, with the admin frontend, the API, the runtime, PostgreSQL, and Redis defined together when that Compose work is actually done. Separate control and game hosts wait until load requires them. k3s, Terraform, and Ansible come after that. One Uvicorn worker remains the rule while live match state stays in process memory.

## Database

The target pair is PostgreSQL plus Redis. Durable player rows belong in PostgreSQL. Redis is cache and temporary shared state. Live match state stays in the runtime. The command channel below is not a Redis queue.

Today, SQLite is the verified development database. PostgreSQL stays unverified until a disposable test URL passes. `DATABASE_URL` is unchanged. Redis stays an optional client and is not part of readiness.

## Game runtime

The target is a separate runtime process in this same repository. FastAPI would send commands to that process. The Python loop remains the authority. ADR-0010 keeps that loop. This record is the decision ADR-0010 left open.

Today the authoritative loop is still in-process in `app/game`. `app/main.py` starts `TickManager` on one Uvicorn worker. `app/game/simulate.py` stays on that path. `game_runtime/session.py`, `game_runtime/benchmark.py`, and `game_runtime/__init__.py` call the same in-process engine for tests and the headless benchmark. They are not a second process.

The empty directories beside `game_runtime/README.md` are reserved names: `combat`, `core`, `entities`, `inventory`, `loot`, `matches`, `movement`, `networking`, `persistence`, `physics`, `players`, `systems`, `teams`, `vehicles`, `weapons`, and `zone`. Splitting the process is not done by adding Python files under those directories. This change adds none.

A folder sketch that adds `app/api/v1/admin/` modules, `workers/`, `shared/`, or `game_runtime/admin_commands/` is a later implementation layout. Those paths are not created here.

## Command boundary

Admin HTTP handlers must not write live match memory or player rows behind the simulation. They send a validated command. The runtime accepts or rejects it and applies a safe change itself.

That channel is a design boundary. It is not implemented. No queue, bus, socket, or package carries admin commands today.

Map publishing that exists today is `app/api/v1/admin_maps.py`, mounted at `/api/v1/admin/maps`. `current_publisher` allows an active account whose username is in the `MAP_PUBLISHERS` list, then `MapService` writes catalog and asset rows. That allow-list is not RBAC. Roles and permissions do not exist.

## Public contract that stays

These routes stay the player API. A future admin prefix does not replace them.

| Area | Existing routes |
| --- | --- |
| Liveness and readiness | `GET /health`, `GET /ready`, `GET /metrics` |
| Accounts | `/api/v1/auth` |
| Profile | `/api/v1/players` |
| Lobby | `/api/v1/lobby` |
| Live matches | `/api/v1/matches` |
| Stored matches | `/api/v1/match-records` |
| Catalog and inventory | `/api/v1/items`, `/api/v1/inventory` |
| Cosmetics wallet | `/api/v1/cosmetics` |
| Public maps | `/api/v1/maps` |
| Map publisher | `/api/v1/admin/maps` |
| Live socket | `/api/v1/ws` |

The cosmetics wallet starts at 500 coin and 20 diamond. The skin catalog is `recruit`, `field_jacket` at 200 coin, and `night_ops` at 15 diamond. Those figures are this server's catalog.

The wire format stays the versioned JSON protocol in `app/networking/protocol.py` and `docs/API_CONTRACT.md`. The original client remains NOT_SUPPORTED. This page names no original opcodes and no new admin protocol fields.

## Proposed admin pages

The prefixes below are a future contract. They are not routes. A later change should mount them on a versioned, authenticated prefix, in the same style as `/api/v1/admin/maps`, and should leave the public `/api/v1` routes in place. The unversioned names are the proposal only.

| Admin page | Proposed prefix | What exists today |
| --- | --- | --- |
| Dashboard | `/admin/dashboard` | No dashboard route. `GET /health` is liveness. `GET /ready` checks the database. `GET /metrics` is Prometheus text. |
| Players | `/admin/players` | `GET /api/v1/players/me` and `PATCH /api/v1/players/me` are the signed-in profile. There is no search, ban, or inspect-any-player route. |
| Lobbies | `/admin/lobbies` | `/api/v1/lobby` is the player lobby API, including the in-memory queue listing. |
| Matches | `/admin/matches` | `/api/v1/matches` lists in-memory matches. `/api/v1/match-records` stores the lifecycle. |
| Maps | `/admin/maps` | Public catalog is `/api/v1/maps`. Publisher routes are `/api/v1/admin/maps`, gated by `MAP_PUBLISHERS`. |
| Weapons | `/admin/weapons` | No admin weapon route. Weapon numbers live in `app/game/items.py`. |
| Items | `/admin/items` | `GET /api/v1/items` is the public catalog. Inventory writes are `/api/v1/inventory` for the caller. |
| Vehicles | `/admin/vehicles` | No admin vehicle route. The boarded buggy uses the local rule in ADR-0009. |
| Gameplay | `/admin/game-config` | No configuration route. Local rules live in `app/game/rules.py`. |
| Rewards | `/admin/rewards` | No rewards route. Stored match rewards are not applied to experience or currency. The wallet is `/api/v1/cosmetics`. |
| Servers | `/admin/servers` | No runtime-control route. Health is `GET /health` and `GET /ready`. |
| Administration | `/admin/users` | No role or permission route. Player login is `/api/v1/auth`. |
| Audit | `/admin/audit-logs` | No audit-log route. |

## Real-time admin views

A live admin dashboard should use the existing WebSocket at `/api/v1/ws` or a later server-sent-events channel. Repeated polling is outside this design. This change adds no socket and no admin event type.

## MVP phases

These phases are a sequence. None of them has started.

| Phase | Deliverable | State |
| --- | --- | --- |
| 1 | Admin API foundation, authentication, and RBAC | Not started. Admin authentication and RBAC do not exist. |
| 2 | Dashboard and server monitoring | Not started. |
| 3 | Player, lobby, and match management | Not started. |
| 4 | Gameplay configuration and audit logs | Not started. |
| 5 | Maps, weapons, items, and vehicles | Not started. Publisher map routes exist and are not this phase. |
| 6 | Rewards, events, and advanced analytics | Not started. |

## Not implemented

- The process split. The loop still starts from `app/main.py`.
- The admin command channel. No queue accepts or rejects admin commands.
- Admin authentication and RBAC. `MAP_PUBLISHERS` is a username allow-list.
- The proposed `/admin/...` routes, including `/admin/dashboard` and `/admin/players`.
- A React, TypeScript, Vite, Tailwind, or shadcn/ui application.
- Python files under the empty `game_runtime` directories.
- A move or rename of `app/game/simulate.py`.
- Docker Compose execution. Compose must not run against the live SQLite file.
- A verified PostgreSQL deployment. `DATABASE_URL` is unchanged.
- Redis as match state, as readiness, or as the command channel.
- Original Rules of Survival opcodes or admin protocol fields. The original client remains NOT_SUPPORTED.
- k3s, Terraform, Ansible, and a separate control host and game host.

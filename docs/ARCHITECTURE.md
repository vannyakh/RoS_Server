# Architecture

This document is the system shape for the private server in this repository. It describes the code that exists today and the boundary of the next design. It is not an original Rules of Survival specification.

The process stays a modular monolith until a new architecture decision splits it. Folder names below are the paths in this repository. A public tree can use different top-level names later. That rename is a separate change, after the behavior is documented and tested.

## 1. System overview

```text
Independent Android client
        |
        |  HTTP JSON and WebSocket JSON
        v
FastAPI control plane  ----  Alembic schema  ----  SQLite now, PostgreSQL intended
        |
        |  in-process calls
        v
Match loop in app/game
        |
        |  finished totals only
        v
Player statistics
```

| Part | Role today | Where it lives |
| --- | --- | --- |
| Android API client | Calls this server's JSON API. It is a separate application from any original game package. | Sibling client project, package `com.ros.client` |
| Control plane | Accounts, sessions, profiles, durable lobbies, inventory, catalogs, stored matches, map publishing | `app/api`, `app/services`, `app/repositories`, `app/models` |
| Authoritative simulation | 20 Hz loop, movement, combat, zone, match lifecycle, in-memory queue | `app/game`, started from `app/main.py` |
| Database | Accounts, durable game records, map metadata | `migrations/versions`, SQLite in development |
| Redis | Optional cache client. It is not in `/ready` and it does not hold match state. | `app/infrastructure/redis.py` |
| Map publishing | Username allow-list, not a full admin console | `app/api/v1/admin_maps.py`, `MAP_PUBLISHERS` |
| Browser page | Static client at `/play` when `assets/play` exists | `app/main.py` |

`GET /health` reports process liveness. `GET /ready` runs `SELECT 1`. Development startup applies Alembic. Production is expected to migrate before serving.

The control plane and the simulation share one process. A second Uvicorn worker would have its own queue and its own matches. Run one worker while live state stays in memory.

## 2. Game runtime

The current runtime is the in-process loop in `app/game`. A later dedicated runtime process would own the same responsibilities and would need a new decision record before the code moves.

Each tick reads `MatchRules` and does not query SQL. Rules in `app/game/rules.py` are local development values: map size, movement speed, queue wait, bot fill, zone radii, and zone damage. They are not original game statistics.

The loop covers:

| Concern | Current behavior |
| --- | --- |
| Game loop | `TickManager` calls `GameEngine.step`. The default rate is 20 Hz. |
| Queue and match start | `lobby.join` queues the account. The queue waits or fills, then starts a match and may add bots. |
| Movement | `player.input` sets move and aim. The tick integrates position on the local map. |
| Combat and weapons | `shoot`, `reload`, `equip`, and `discard` update in-memory loadouts. Weapon numbers live in `app/game/items.py`. |
| Inventory inside a match | Pickup, use, and equip change the live loadout. Durable stacks are a separate HTTP inventory. |
| Vehicles | Board and exit use the local buggy rule in ADR-0009. |
| Zone | Radii and damage step on the local schedule. |
| Match end | Placement and kills stay on the in-memory result. Persistence then adds kills, wins, and matches played. Experience and currency rewards are not granted. |

World keys are account ids. Durable lobby membership, inventory, and stored match participants use player ids. `GET /api/v1/players/me` returns both.

## 3. Networking

Clients use the versioned JSON contract in `docs/NETWORK_PROTOCOL.md` and `docs/API_CONTRACT.md`.

| Flow | Current contract |
| --- | --- |
| Connection | `ws://<host>:8000/api/v1/ws`. The token is the first JSON `auth` payload, not a query parameter. |
| Authentication | HTTP `Authorization: Bearer`. The server checks the JWT and the stored session hash. Logout revokes that hash only. |
| Input | `player.input` and `player.action`. Actions include shoot, reload, pickup, use, equip, jump, discard, board, and exit. |
| Snapshots | The tick sends `state` to the current socket for that account. |
| Reconnection | A new socket for the same account closes the previous socket. The client sends `auth` again. |
| Durable rooms | HTTP lobby and match-record routes. They do not drive the in-memory queue. |

Message types and fields are the ones implemented in `app/networking/protocol.py` and `app/networking/websocket.py`. A binary or protobuf protocol is not adopted. Choosing one later is an architecture decision with tests, written beside the code that implements it.

Original client packet research stays in `docs/reverse-engineering/`. It is not copied into this contract.

## 4. Data architecture

Schema revisions live in `migrations/versions`. The initial revision is `93510e8bf194`. Map content versions are `b7e2c91a4d10`. Primary keys are UUID strings so SQLite and PostgreSQL can share a revision. PostgreSQL is the intended production database and stays unverified until a disposable `POSTGRES_TEST_URL` test passes.

| Data | Store |
| --- | --- |
| Accounts and sessions | `accounts`, `account_sessions`. Passwords are Argon2 hashes. Only the SHA-256 of a token is stored. |
| Profiles and totals | `players`, `player_statistics`. One player per account. |
| Durable rooms | `lobbies`, `lobby_members`, `teams`, `team_members`. |
| Stored matches | `matches` and result rows. Live coordinates are not columns. |
| Catalogs | Items, modes, weapons, equipment, vehicles, ranks, achievements. `TEST_*` codes are fixtures. |
| Map packages | Metadata in SQL. Bytes under `storage/game_assets`. Clients receive bytes, not disk paths. |
| Live match | `WorldState` in memory. Finished totals are written after the tick. |

`docs/DATABASE_SCHEMA.md` and `docs/MAP_SYSTEM.md` hold the table detail. High-frequency position, aim, and health stay out of the database.

## 5. AI agent workflow

```text
Agent receives a task
        |
        v
Read AGENTS.md
        |
        v
Read docs/ARCHITECTURE.md and the module document
        |
        v
Inspect the code and tests
        |
        v
Plan one module
        |
        v
Implement that module
        |
        v
Run tests and static checks
        |
        v
Write the implementation report
        |
        v
Human review and merge
```

Task ownership stays in `.cursor/management/tasks.json`. The CTO assigns work. Specialists edit only the paths their task allows. Two active tasks do not share a write path.

Agents do not invent API paths, mix account ids with player ids, or treat a local simulation number as an original game value. Compatibility status changes only through `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` and its evidence rules.

## 6. Deployment

| Environment | Current practice |
| --- | --- |
| Local development | SQLite file, one Uvicorn worker, Alembic on startup, `GET /health` and `GET /ready`. |
| Android development | The API client uses `http://127.0.0.1:8000` through `adb reverse`. A LAN address is supplied at runtime and is not committed. |
| Docker | Compose files exist for a future isolated database. They are not a release, and they are not run against the live SQLite file. |
| Production | Run Alembic before serving. Use a disposable PostgreSQL URL for verification. Keep secrets in the environment. |
| Monitoring | Prometheus metrics and request ids are installed. Player ids are not metric labels. Logs omit passwords, raw tokens, and session hashes. |
| Scaling | One process owns the live match. Horizontal workers wait until match state has a shared authority. |

`docs/operations/RELEASE_STATUS.md` records why the tree is not a release.

## Licensing boundary

A future open-source license can cover code written for this server. It does not grant rights to publisher binaries, artwork, sounds, or other proprietary assets. Those files stay out of the public tree. Asset policy and source license stay separate documents.

## Later documents

These pages are the next design notes. They are not written by this overview:

| Page | Will define |
| --- | --- |
| `docs/GAME_RUNTIME.md` | The authoritative simulation when it is split from the control plane |
| `docs/NETWORK_PROTOCOL.md` | Written. Version 1 JSON for this server. |
| `docs/ROADMAP.md` | Public milestones. The engineering roadmap today is `docs/project/MASTER_ROADMAP.md` |

Until those pages exist, `docs/API_CONTRACT.md`, `docs/SERVICE_ARCHITECTURE.md`, and `docs/DATABASE_SCHEMA.md` are the detailed references.

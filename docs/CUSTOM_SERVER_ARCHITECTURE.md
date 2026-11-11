# Custom server architecture

Date: 2026-11-11. This page describes the server in this repository. The system overview in `docs/ARCHITECTURE.md` remains the module map. This page states who may connect.

The original Android client, package `com.netease.chiji` versionName `1.610637.617289`, is not a supported client. It stopped on the patch-gate text and does not speak this server's JSON. The supported independent app is `Android_API_Client`, package `com.ros.client`, in the sibling client repository.

## Shape

```text
com.ros.client  (and /play when assets/play exists)
        |
        |  HTTP JSON and WebSocket JSON, version 1
        v
FastAPI control plane
  accounts, sessions, profiles, lobbies, catalogs, maps, results
        |
        |  in-process calls
        v
Match loop in app/game
        |
        |  finished totals only
        v
Player statistics
```

`com.netease.chiji` is outside this drawing. Its protocol is UNKNOWN. Its compatibility outcome is NOT_SUPPORTED.

## Parts

| Part | What exists | Status |
| --- | --- | --- |
| Control plane | FastAPI routes under `app/api`, services, repositories, and SQLAlchemy models. `GET /health` is liveness. `GET /ready` runs `SELECT 1`. | CONFIRMED in `docs/ARCHITECTURE.md` |
| Session | Argon2 password hashes. Access tokens stored as SHA-256 hashes. Logout revokes that hash only. WebSocket `auth` carries the token in the JSON payload. | CONFIRMED in `docs/NETWORK_PROTOCOL.md` and `app/networking/protocol.py`. NOT_SUPPORTED for the original APK |
| Live protocol | One JSON object per text frame: `version` 1, `type`, `sequence`, `payload`. Client types are `auth`, `heartbeat`, `player.input`, `player.action`, `lobby.join`, `lobby.leave`, and `match.forfeit`. | CONFIRMED as the literals in `app/networking/protocol.py`. DOCUMENTED in `docs/NETWORK_PROTOCOL.md`. NOT_SUPPORTED for the original APK |
| Lobby | HTTP creates durable rooms, members, and teams. The socket queue is separate and uses account ids. | CONFIRMED in `docs/ARCHITECTURE.md`. NOT_SUPPORTED for the original APK |
| Matchmaking | In-memory queue in `app/game`. One Uvicorn worker owns that memory. | CONFIRMED. NOT_SUPPORTED for the original APK |
| Simulation | `app/game` steps movement, weapons, zone, loot, and the buggy rule. The tick does not query SQL. Empty `game_runtime/*` names stay reserved and are not a second engine. | CONFIRMED. Numbers are the independent design in `docs/GAME_RULES.md` |
| Cosmetics wallet | Starter 500 coin, 20 diamond, and skins `recruit`, `field_jacket`, `night_ops` | CONFIRMED in `app/services/cosmetics_service.py`. Independent catalog. NOT_SUPPORTED for the original APK |
| Maps | Metadata in SQL. Bytes under `storage/game_assets`. Clients receive bytes. Publishing uses the username allow-list `MAP_PUBLISHERS` on `app/api/v1/admin_maps.py`. The live tick does not load terrain from a published package. | CONFIRMED as this server's content path. Original terrain is UNKNOWN |
| Match results | Kills, wins, and matches played are written after the tick. Experience and currency rewards are not granted. | CONFIRMED in `docs/GAMEPLAY_SYSTEMS.md`. NOT_SUPPORTED for the original APK |
| Data store | SQLite in development. PostgreSQL is the intended production database and stays unverified until a disposable test URL passes. Redis is optional and does not hold match state. | DOCUMENTED in `docs/ARCHITECTURE.md` |
| Admin application | The sibling admin repository contains `AGENTS.md` and `docs/ARCHITECTURE.md` only. No console is built. | DOCUMENTED. P2 admin protocol of the original game is UNKNOWN |
| Updates | This process has no patch-list exchange for the original client. | NOT_SUPPORTED. The original patch-list format is UNKNOWN |

## Process boundary

The control plane and the simulation share one process, which matches the current architecture decision. A second worker would have its own queue and its own matches. Horizontal workers wait until live match state has a shared authority.

`docs/GAME_RUNTIME.md` describes the same tick. Splitting it into another operating-system process needs a new decision before the code moves.

## Clients that are in scope

| Client | Relationship |
| --- | --- |
| `com.ros.client` | Independent Kotlin client. It sends this server's HTTP and WebSocket JSON. |
| Browser page at `/play` | Static client of this server when `assets/play` exists. |
| `com.netease.chiji` | Research reference. NOT_SUPPORTED. Startup CONFIRMED only through the patch gate. |

Account registration, durable lobby routes, and the live socket are specified in `docs/API_CONTRACT.md` and `docs/NETWORK_PROTOCOL.md`. A new message type belongs in `app/networking/protocol.py` together with a test. It is not imported from the original package.

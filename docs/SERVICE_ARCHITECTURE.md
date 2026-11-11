# Service architecture

Confirmed fact. The running server is one FastAPI process. `app/main.py` builds the app, mounts the routers, and starts one 20 Hz tick. There are no separate deployable services.

The folders were not reorganized to match a green-field tree. The mapping below is the logical boundary. The path is where the code actually lives.

| Logical module | Responsibility | Actual location |
| --- | --- | --- |
| Auth | Register, login, logout, session checks | `app/api/v1/auth.py`, `app/services/auth_service.py`, `app/services/account_service.py`, `app/core/security.py` |
| Players | Profile read and the two writable profile fields | `app/api/v1/players.py`, `app/services/player_service.py` |
| Lobbies | Durable rooms, ready, capacity, empty-room close | `app/api/v1/lobby.py`, `app/services/lobby_service.py` |
| Teams | Team create, join, and leave inside a lobby | same lobby service and router |
| Inventory | Catalog stacks and currency balances | `app/api/v1/inventory.py`, `app/api/v1/items.py`, `app/services/inventory_service.py` |
| Matchmaking | In-memory queue and match assignment | `app/game/engine.py`, `app/game/simulate.py`, WebSocket `lobby.join` |
| Matches | Stored lifecycle separate from the live match | `app/api/v1/match_records.py`, `app/services/match_service.py` |
| Realtime | Authenticated sockets and disconnects | `app/networking/websocket.py`, `app/networking/connection_manager.py` |
| Operations | Liveness, readiness, metrics | `app/api/v1/health.py`, `app/observability/` |

Dependency direction stays `app/api` to `app/services` to `app/repositories` to `app/models`. The tick does not query SQL. A finished in-memory match can write kill, win, and match totals through `app/services/persistence_service.py` after the tick returns the result.

## Identity

Confirmed fact. An account is the login. A player is the profile, one per account. Tokens use the account id as `sub`. The WebSocket and the in-memory world also use the account id. Lobby members, inventory, and stored match participants use the player id.

Interpretation. An Android client should keep both ids from `GET /api/v1/players/me` and use the player id for lobby and match-record bodies.

## Auth

Confirmed fact. Login creates a random JWT (`jti` plus expiry) and stores only its SHA-256 hash in `account_sessions`. `account_for_token` rejects a missing hash, a hash owned by another account, a revoked row, and an expired row. Logout sets `revoked_at` for that token only.

The login failure counter is in process memory, five failures per host per 60 seconds. It is not shared across processes.

## Durable lobby and teams

Confirmed fact. Join increments `current_players` only when the lobby is `open` and `current_players < max_players`, then inserts the member in the same transaction. The unique pair `(lobby_id, player_id)` rejects a duplicate insert. SQLite connections wait up to 5 seconds on a write lock so two joins can serialize.

Confirmed fact. There is no leader column on `lobbies`, `lobby_members`, or `teams`. This server's rule is: every member has the same permissions, and the lobby closes when its last member leaves. A future leader role needs a new column and a new migration. None was added.

Confirmed fact. Team membership is unique per lobby and player. Leaving a team does not leave the lobby. Leaving the lobby removes the team seat as well.

## Inventory

Confirmed fact. Catalog rows live in `item_definitions`. Owned stacks live in `inventory_items` with `quantity >= 0` and one row per inventory and item. Currency balances cannot go below zero. Mutations commit in `InventoryService`.

Confirmed fact. `equipment_definitions` is a catalog table. There is no player equipment or slot table. The live `equip` action changes in-memory match state only.

Confirmed fact. `POST /api/v1/inventory/items` and `POST /api/v1/inventory/currency` let the authenticated player change their own rows. They are not restricted to a match payout.

## Matchmaking

Confirmed fact. The queue is the in-memory `WorldState`. `lobby.join` is idempotent while the player is already queued. A player in `countdown`, `dropping`, or `alive` is not queued again. The queue waits `queue_wait_seconds` (default 2) or fills to `max_players_per_match`, then starts a match and may add bots up to `bot_fill`.

Limitation. That queue is local to one process. A second Uvicorn worker would have its own queue and its own matches. Redis is not used for matchmaking. Do not run more than one worker while live state stays in memory.

The durable `match-records` API does not read or write this queue. See `docs/architecture/decisions/ADR-0008-match-records.md`.

## Stored matches and rewards

Confirmed fact. `MatchService` is the durable lifecycle. High-frequency positions stay in memory. Finalize writes `match_results` and `match_statistics` once, then sets `completed`. The unique result row and the status check both reject a second completion.

Decision. Experience, currency, and item rewards are not granted. `match_results.rewards` is stored as supplied and is not interpreted. No original reward table is in this repository, and earlier checkpoints kept payouts unimplemented until a local rule exists. The live match path still adds kills, wins, and matches played when an in-memory match ends. That path does not read the stored `rewards` object.

A stored participant is locked to one active stored match by updating the player row and then checking for another `scheduled`, `lobby`, or `running` seat in the same transaction. Two concurrent joins can still race on PostgreSQL if the player row update does not block; SQLite serializes the writes. There is no partial unique index for this rule.

## Realtime

Confirmed fact. The socket accepts, waits for `auth`, checks the session, then registers the socket. One account has one current socket. Heartbeats are echoed. Disconnect clears that socket only if it is still the current one, and a queued player leaves the in-memory queue.

A session lookup that fails for a reason other than `AppError` is logged as the exception type and reported to the client as an invalid token. The token and the session hash are not written in that log line.

## Operations

Confirmed fact. `/health` is liveness. `/ready` is database readiness. Optional Redis is not part of readiness. HTTP responses include `x-request-id`. Prometheus metrics are already installed. Logs must not contain passwords, raw tokens, or session hashes.

Development applies `alembic upgrade head` on startup. Production is expected to run that command itself. The development URL is SQLite. PostgreSQL is the intended production database and is not treated as verified until `POSTGRES_TEST_URL` points at a disposable database and the integration test passes.

## Compatibility

Confirmed fact. Local tests do not make a feature compatible with original Rules of Survival. The matrix stays `unknown` for every row. Details are in `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` and `docs/API_CONTRACT.md`.

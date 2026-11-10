# Architecture audit

Read-only inspection of the Python tree under `app/` on 2026-11-10. Every finding is labeled from the files that were opened or searched. This file does not change application code or `.cursor/management`.

Labels:

- **Confirmed fact** — present in a file that was read or in a repository search.
- **Interpretation** — a conclusion drawn from those facts.
- **Hypothesis** — a possible consequence that this audit did not execute.
- **Unknown** — not established by the files read.

TASK ID: unassigned audit
AGENT: backend-architect
PHASE: inspection
STATUS: report only

IMPLEMENTATION:
FILES CREATED: reports/project-audit/architecture.md
FILES MODIFIED:
DISCOVERIES: see sections below
DATABASE CHANGES: none
API CHANGES: none
GAME FUNCTION CHANGES: none
TESTS EXECUTED: none (read-only audit)
TEST RESULTS:
COMPATIBILITY EVIDENCE: none
KNOWN ISSUES: see Risks
RECOMMENDATION: keep the working split; do not merge the live world into the SQL match and lobby services

OBJECTIVE: Map the modules that exist, the import direction, the FastAPI entrypoint, the tick, and where gameplay state lives.
IMPLEMENTATION SUMMARY: One report. No application edits.
SECURITY CONSIDERATIONS: Auth reads are described only as the call path that exists. No secrets were read.
DEPENDENCIES: none

## Module map

**Confirmed fact.** `app/` contains these packages, each with an `__init__.py`: `api` (`api/v1`), `core`, `database` (`seeds`, `importers`), `game`, `infrastructure`, `models`, `networking`, `observability`, `repositories`, `schemas`, `services`. `app/services/__init__.py` and `app/game/__init__.py` are empty. There is no `app/workers` package and no second process module in the 85 Python files under `app/`.

**Confirmed fact.** HTTP and WebSocket registration is only in `app/api/router.py`:

| Mount | Module | What the handler calls |
| --- | --- | --- |
| `/health`, `/version.cfg` | `app/api/v1/health.py` | A status dict, or `FileResponse` for `assets/configurations/version.cfg` |
| `/api/v1/auth` | `app/api/v1/auth.py` | `app.services.auth_service` |
| `/api/v1/players` | `app/api/v1/players.py` | `app.services.player_service.profile_for_account` |
| `/api/v1/lobby` | `app/api/v1/lobby.py` | `lobby_status()` for GET; `LobbyService` for POST |
| `/api/v1/matches` | `app/api/v1/matches.py` | `app.services.matchmaking_service` |
| `/api/v1/items` | `app/api/v1/items.py` | `GameDataService` |
| `/api/v1/ws` | `app/networking/websocket.py` | `game_engine` after a direct `Account` lookup |

**Confirmed fact.** `app/main.py` also mounts `/play` from `assets/play` when that directory exists. Whether `assets/play` exists was not checked.

**Confirmed fact.** Service modules that exist: `account_service.py`, `auth_service.py`, `game_data_service.py`, `inventory_service.py`, `lobby_service.py`, `match_service.py`, `matchmaking_service.py`, `persistence_service.py`, `player_service.py`.

**Confirmed fact.** Repository modules that exist: `account_repository.py`, `game_data_repository.py`, `inventory_repository.py`, `lobby_repository.py`, `match_repository.py`, `player_repository.py`.

**Confirmed fact.** `app/models/__init__.py` exports 30 mapped classes. Their `__tablename__` values are:

- Account: `accounts`, `account_sessions`, `account_devices`, `login_history`
- Player: `players`, `player_statistics`, `player_progression`
- Catalog: `game_modes`, `map_definitions`, `item_definitions`, `weapon_definitions`, `equipment_definitions`, `vehicle_definitions`, `rank_definitions`, `achievement_definitions`
- Inventory: `player_inventories`, `inventory_items`, `player_currencies`, `currency_transactions`
- Match: `matches`, `match_participants`, `match_results`, `match_statistics`
- Lobby: `lobbies`, `lobby_members`, `teams`, `team_members`
- Configuration: `server_configurations`, `game_configurations`, `feature_configurations`

**Confirmed fact.** `app/game/` is `engine.py`, `simulate.py`, `state.py`, `rules.py`, `items.py`, and `tick_manager.py`. `app/networking/` is `websocket.py`, `protocol.py`, `validation.py`, and `connection_manager.py`. `app/infrastructure/` is `database.py`, `redis.py`, and `storage.py`.

**Confirmed fact.** Schema modules exist for account, auth, common, configuration, game_data, inventory, lobby, match, and player. `app/api/router.py` has no configuration or inventory route. `app/api/v1/matches.py` returns the dict from the in-memory view and does not use `app/schemas/match.py`.

**Confirmed fact.** `FeatureConfiguration`, `GameConfiguration`, `ServerConfiguration`, and `PlayerProgression` are defined and exported. A search of `app/` found no service or route that constructs or queries them.

**Unknown.** Alembic revision files and the live database contents were not opened for this audit. Table names above are the ORM declarations, not a dump of a database.

## Import direction

The rule file `.cursor/rules/01-architecture.mdc` describes `api -> services -> repositories -> models`, and `networking` and `game` depending on `services`. The imports below are what the code does.

**Confirmed fact.** These edges match that direction:

- `app/api/v1/auth.py`, `items.py`, `players.py`, `lobby.py`, and `matches.py` call services.
- `account_service`, `inventory_service`, `lobby_service` (the class), `match_service`, `game_data_service`, and `player_service` call repositories.
- Repositories import `app.models` and SQLAlchemy `select`.
- `app/game/simulate.py` imports `logging`, `math`, `random`, `uuid`, and `app.game.items`, `app.game.rules`, `app.game.state`.
- `app/game/engine.py` imports `asyncio` and `app.game` modules only.
- `app/game/state.py` imports `dataclasses` and `time.monotonic`.
- `app/networking/protocol.py` imports `pydantic` only.

**Confirmed fact.** These edges cross the written direction:

- `app/api/dependencies.py` constructs `AccountRepository` and `PlayerRepository` and returns ORM `Account` and `Player`.
- `app/api/v1/lobby.py` and `app/api/v1/players.py` import ORM types for annotations.
- `app/api/router.py` includes `app.networking.websocket.router`.
- `app/services/lobby_service.py` and `app/services/matchmaking_service.py` import `app.game.engine.game_engine`.
- `app/services/persistence_service.py` imports `SessionLocal` and runs `select` on `Player` and `PlayerStatistics`. It does not use a repository.
- `app/networking/websocket.py` imports `game_engine`, `SessionLocal`, and `app.models.account.Account`. It does not call a service.
- `app/game/rules.py` imports `app.core.config.settings`.
- `app/game/tick_manager.py` imports `app.observability.metrics.observe_tick`. `app/observability/metrics.py` imports `sqlalchemy.event`.
- `app/database/importers/` imports services, repositories, and models.
- Model modules import `Base` from `app.infrastructure.database`.

**Interpretation.** The game package does not depend on services or SQLAlchemy sessions. The process entrypoint and the WebSocket module are the composition root that joins the world to the database. Services that expose the live queue depend on the game engine, which is the reverse of the arrow in the architecture rule.

## Entrypoint and the 20 Hz tick

**Confirmed fact.** `app/main.py` builds one `FastAPI` app named from `settings.app_name`, version string `"2.0.0"`, with lifespan `lifespan`. `register_routes(app)` runs at import. `install_http_instrumentation(app)` runs after that.

**Confirmed fact.** `app/core/config.py` sets `game_tick_rate: int = 20`. `Settings` loads `env_file=".env"`. `.env` was not read.

**Unknown.** The tick rate of a running process, if an environment variable overrides the default.

**Confirmed fact.** Lifespan in `app/main.py`:

1. `configure_logging()`.
2. `await init_db()` when `settings.app_env == "development"`.
3. `TickManager(settings.game_tick_rate, _tick)` stored on `app.state.tick_manager`.
4. `app.state.engine = game_engine`.
5. `asyncio.create_task(tick.run())`.
6. On shutdown: `tick.stop()`, cancel that task, `await get_cache().close()`, `await close_db()`.

**Confirmed fact.** `app/infrastructure/database.py` `init_db` returns immediately unless `app_env == "development"`, then runs `alembic upgrade head` in a subprocess via `asyncio.to_thread`. A search of `app/**/*.py` found no `create_all` call. The words `create_all` appear only in the module docstring of `app/models/__init__.py`.

**Confirmed fact.** `TickManager` in `app/game/tick_manager.py` rejects a rate outside 1..60, sets `interval = 1.0 / tick_rate`, and loops with `monotonic` and `asyncio.sleep`. Each pass `await`s the callback with `self.interval`, increments `self.tick`, then calls `observe_tick`. If the callback takes longer than `interval`, it logs a warning and sets `next_tick = monotonic()`, so the loop does not try to catch up missed intervals.

**Confirmed fact.** The callback `_tick` in `app/main.py` does four things in order:

1. `snapshots = await game_engine.step(dt)`.
2. `await connection_manager.publish_states(snapshots)`.
3. `for result in await game_engine.take_results(): await persistence_service.save_player_progress(result.player_id, {"kills": result.kills, "win": result.win})`.
4. `observe_world(game_engine.world)`.

**Confirmed fact.** `GameEngine.step` holds `self._lock`, increments `world.tick`, calls `simulate(world, dt, self.rules)`, builds snapshots for connected non-bot players, clears each match's `events`, and returns the snapshots. `take_results` holds the same lock, copies `world.pending_results`, and clears the list.

**Confirmed fact.** `PersistenceService.save_player_progress` opens `async with SessionLocal()`, selects `PlayerStatistics` by `Player.account_id == player_id` and, if that misses, by `PlayerStatistics.player_id == player_id`, then adds `kills`, increments `total_matches`, increments `total_wins` when `win` is true, and commits. Exceptions are logged and swallowed. The method's docstring says durable writes stay outside the game tick. The only caller under `app/` is `_tick`.

**Interpretation.** Simulation and the engine lock finish before the database call. The database call still runs inside `TickManager.run`'s awaited callback, so a slow commit delays the next tick and can take the overrun branch in `tick_manager.py`.

**Confirmed fact.** `observe_world` reads `world.players` and `world.matches` with no lock. WebSocket handlers mutate the same `WorldState` under `GameEngine._lock`.

**Hypothesis.** A tick that reaches `observe_world` while a WebSocket handler mutates `world.players` can hit a dict-size change during iteration. This audit did not run that interleaving.

## Gameplay state is in memory

**Confirmed fact.** `app/game/engine.py` ends with `game_engine = GameEngine()`. `GameEngine.__init__` sets `self.world = WorldState()` and `self._lock = asyncio.Lock()`. `reset_state` replaces `self.world` with a new `WorldState`.

**Confirmed fact.** `app/game/state.py` defines `PlayerState`, `LootNode`, `MatchResult`, `Match`, and `WorldState` as dataclasses. `PlayerState` holds `x`, `y`, `z`, `health`, movement and aim, `weapon`, `mag`, `inventory: dict[str, int]`, `mags`, `kills`, `status`, and `match_id`. `WorldState` holds `players`, `matches`, `pending_results`, `tick`, and `time`. `app/models/player.py` columns are `account_id`, `nickname`, `avatar_id`, `level`, `experience`, and `status`. `app/models/match.py` has no position or aim columns. Its module docstring says positions and aim stay in memory.

**Confirmed fact.** `app/game/simulate.py` module docstring says the module does no I/O. `_record_results` appends an in-memory `MatchResult` (player id, kills, win, placement) for human players. `random.Random` is seeded from `match_id` and from `match_id` plus `zone_index`.

**Confirmed fact.** `app/game/items.py` is a module-level `WEAPONS`, `HEALS`, and `LOOT_TABLE` dict/tuple. It does not import SQLAlchemy or the catalog models.

**Confirmed fact.** `app/networking/connection_manager.py` stores `dict[str, WebSocket]` on a module singleton `connection_manager`. `connect` replaces any previous socket for that id and closes it with code 4000. `publish_states` sends `{"version": 1, "type": "state", "sequence": snapshot["tick"], "payload": snapshot}`.

**Confirmed fact.** WebSocket auth in `app/networking/websocket.py` decodes the JWT, reads `sub`, loads `Account` with `session.get(Account, player_id)`, and uses `account.id` as the id passed to `connection_manager.connect` and `game_engine.connect`. `app/services/account_service.py` creates that token with `create_access_token(account.id)`. `app/core/security.py` puts that argument in the `sub` claim.

**Confirmed fact.** HTTP lobby membership uses `Player.id` from `current_player` (`app/api/dependencies.py` loads `Player` by `account_id`). SQL `lobby_members.player_id` and `match_participants.player_id` are foreign keys to `players.id` (`app/models/lobby.py`, `app/models/match.py`).

**Interpretation.** The live world key for a WebSocket client is `accounts.id`. The durable lobby and match-participant key is `players.id`. Nothing in the handlers copies one into the other.

**Confirmed fact.** Two lobby paths exist side by side:

- `GET /api/v1/lobby` calls `lobby_status()` which returns `game_engine.lobby_status()` / `lobby_view` (queued in-memory players).
- `POST /api/v1/lobby` and the member and team routes call `LobbyService`, which inserts `Lobby`, `LobbyMember`, and `Team` rows and commits.

`LobbyService` does not call `game_engine.join_queue`. The WebSocket `lobby.join` handler calls `game_engine.join_queue` and does not call `LobbyService`.

**Confirmed fact.** Two match paths exist side by side:

- `GET /api/v1/matches` and `GET /api/v1/matches/{match_id}` call `matchmaking_service`, which returns `matches_view` / `match_view` from `WorldState.matches`.
- `MatchService` in `app/services/match_service.py` creates and finalizes SQL `matches`, `match_participants`, `match_results`, and `match_statistics`. A search of `app/` found no caller of `MatchService`. Callers exist under `tests/`.

**Confirmed fact.** The tick persistence payload is `{"kills": result.kills, "win": result.win}`. `placement` is on the dataclass and is not passed. The update touches `player_statistics` counters only. It does not insert `match_results`.

**Confirmed fact.** `InventoryService` is constructed from `app/database/importers/inventory_importer.py`. A search of `app/api` and `app/game` found no `InventoryService` import. Live loadout changes go through `game_engine.perform` into `PlayerState.inventory`.

**Confirmed fact.** `app/services/auth_service.py` keeps login failures in a module dict `_failures`, 5 failures inside 60 seconds per host string.

**Confirmed fact.** `app/infrastructure/redis.py` defines `RedisCache.get` and `set`. A search of `app/` found `get_cache()` only in `app/main.py`, and that call is `close()` during shutdown. `close` does nothing when no client was created. `Redis.from_url` runs on the first `get` or `set`.

**Interpretation.** Positions, aim, health, the live queue, live matches, sockets, and the login counter are process memory on the module singletons. Redis is not a store for that state. Durable rows written from the running server path that was read are account/session/login rows from `AccountService`, lobby and team rows from `LobbyService`, catalog reads from `GameDataService`, and `player_statistics` increments from `PersistenceService`.

**Hypothesis.** A second OS process running `app.main:app` would have its own `game_engine`, `connection_manager`, and `_failures` dict. README and `docs/DATABASE_OPERATIONS.md` show `uvicorn app.main:app` without `--workers`. The worker count of any other launch was not read.

## Working boundaries

These are the seams the current code already uses. Recommendations below leave them in place.

**Confirmed fact.** `simulate` mutates the `WorldState` it is given and performs no session or socket work. Callers in `GameEngine` hold `asyncio.Lock` before calling it. WebSocket input, queue, forfeit, and actions use the same lock.

**Confirmed fact.** The JSON contract for client messages is `app/networking/protocol.py`: version literal `1`, types `auth`, `heartbeat`, `player.input`, `player.action`, `lobby.join`, `lobby.leave`, and `match.forfeit`. `app/networking/validation.py` supplies size, rate, and sequence checks used by the WebSocket loop.

**Confirmed fact.** Account registration and login go `auth route -> auth_service -> AccountService -> AccountRepository` / `PlayerRepository`, and the service commits. Login inserts `AccountSession` with `token_hash` from `hash_token`.

**Confirmed fact.** `current_account` and `_player_id_for_token` load `Account` by the JWT `sub` and require `status == "active"`. A search of `app/` found `AccountSession` used in the model and written in `AccountService.login`. No `app/` reader of `token_hash` appeared in that search.

**Confirmed fact.** `GET /api/v1/items` is `GameDataService` to `GameDataRepository` over `ItemDefinition`. `GET /api/v1/players/me` is `profile_for_account` to `PlayerRepository`.

**Confirmed fact.** `MatchService` docstring says it is not the live simulation. `lobby_service.py` docstring says the live queue remains in memory. The route prefixes match that split: GET reads memory, POST lobby routes write SQL.

**Interpretation.** The durable lobby API and the live queue are separate products that share a URL prefix and a service module, and they already have separate functions (`LobbyService` versus `lobby_status`).

## Risks

**Confirmed fact.** Result rows are removed from `pending_results` before `save_player_progress`. A database exception is logged inside that method and is not re-raised, and the list is already empty.

**Interpretation.** A failed statistics write drops that in-memory result for the rest of the process lifetime. The tick continues.

**Confirmed fact.** Statistics updates run on the tick callback. `TickManager` treats a slow callback as an overrun and skips catch-up.

**Hypothesis.** A commit that exceeds 50 ms at the default rate moves the following tick later by that overrun. This audit did not time a commit.

**Confirmed fact.** `save_player_progress` looks up statistics by account id, then by player id, and returns without writing when both miss. Bots are excluded in `_record_results`. Human ids that match neither column produce no row change.

**Confirmed fact.** `MatchService.finalize` is the writer for `match_results` and `match_statistics`. The tick path does not call it. Live match end updates `player_statistics` only, and only kills, match count, and wins.

**Interpretation.** SQL match history and the live match are not the same record. A client of `GET /api/v1/matches` sees `WorldState`. A client of the SQL tables sees rows created outside the tick.

**Confirmed fact.** WebSocket queue identity is `accounts.id`. SQL lobby join uses `players.id`. The two lobby operations do not call each other.

**Interpretation.** A player who only uses `POST /api/v1/lobby/{id}/members` is absent from `lobby_view` until some other call hits `game_engine.join_queue` with the account id.

**Confirmed fact.** `observe_world` and the statistics commit sit outside `GameEngine._lock`. Snapshots passed to `publish_states` are dicts built under the lock.

**Confirmed fact.** Login failure state and the world are module globals. `RedisCache.get` and `set` have no callers in `app/`.

**Interpretation.** Restarting the process clears positions, the queue, open sockets, and the login counter. Account rows and any statistics already committed remain in the database.

**Confirmed fact.** `app/api/dependencies.py` is an API module that queries repositories. `app/networking/websocket.py` queries `Account` with its own `SessionLocal`.

**Interpretation.** Those two reads duplicate the "active account" check and sit outside `AccountService`. They are small and already working. Folding them into a service would be a move, not a bug fix required to keep the tick running.

## Recommended changes

Do not rewrite `simulate`, the engine lock, the auth route, or the protocol models. The following are boundary notes for later tasks.

1. Leave `app/game/simulate.py` and `app/game/state.py` free of SQLAlchemy and sockets. New combat or movement behavior belongs in those modules. New durable tables belong with the database engineer and a service, not in the tick function.

2. Keep `GET /api/v1/lobby` and `GET /api/v1/matches` on `game_engine`. Keep `LobbyService` and `MatchService` as the SQL writers they already are. A later task can document the two identifiers (`accounts.id` in the world, `players.id` in SQL) in the service docstrings. Connecting them means an explicit lookup, owned by one task, not a change to `PlayerState` fields.

3. Keep match-end SQL on `PersistenceService`. If a later task must stop the tick from waiting on that commit, move the `await save_player_progress` to a queue drained after `TickManager` returns from the callback. Leave `step` and `take_results` as they are until that task exists. Copy `pending_results` out and clear them only after a successful commit if that task is asked to avoid losing a failed write. That is a behavior change and needs its own test.

4. Do not route the live world through `RedisCache`. The class is unused for reads and writes. Shutdown `close()` can stay.

5. Do not add an official-protocol adapter beside `app/networking/protocol.py`. Client messages stay on the version-1 models already parsed in `websocket.py`.

6. `current_account` and the WebSocket account lookup can stay where they are until an auth task needs one policy for both. `AccountSession.token_hash` is written at login and has no reader under `app/`. A revocation check would be new behavior, not a boundary cleanup.

7. `MatchService`, `InventoryService`, configuration models, and `PlayerProgression` are implemented and unused by the HTTP and tick paths. Leave them. Wiring the tick to `MatchService.finalize` would write a second match record and should be a separate task that names the id mapping first.

8. `app/api/v1/matches.py` raises `HTTPException`. Other routes use `AppError`, which `app/main.py` renders as `{"detail": ...}`. Aligning that one handler is optional and local to `matches.py`.

## Unknown

- The value of `game_tick_rate`, `database_url`, and `app_env` in a running environment. Defaults are in `app/core/config.py`. `.env` was not read.
- Whether `assets/play` exists, so whether `/play` is mounted.
- Alembic head, applied revisions, and row counts.
- Process count and whether more than one uvicorn worker is used outside the commands in `README.md` and `docs/DATABASE_OPERATIONS.md`.
- Timing of `save_player_progress` against the 50 ms default interval.
- Whether `observe_world` has thrown `RuntimeError` under load.

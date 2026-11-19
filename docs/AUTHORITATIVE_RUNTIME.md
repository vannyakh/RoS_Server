# Authoritative runtime

Audit date: 2026-11-11. This page records the simulation that already runs. A claim that movement, physics, combat, vehicles, and match simulation still need to be built is stale. The numbers below are this server's development rules. They are not original Rules of Survival values. Original-client compatibility is not claimed.

Related pages: `docs/GAME_RUNTIME.md`, `docs/GAMEPLAY_SYSTEMS.md`, `docs/ARCHITECTURE.md`, `docs/CUSTOM_SERVER_ARCHITECTURE.md`, `docs/NETWORK_PROTOCOL.md`, `docs/ENGINE_EVALUATION.md`.

## What already runs

The server owns the live world. `app/game/engine.py` `GameEngine` holds a `WorldState` and advances it only from `step` or a player action. `app/game/simulate.py` `simulate` performs the step and imports no SQLAlchemy session. `game_runtime/session.py` `AuthoritativeSession` wraps that engine for a two-player world. Its module docstring states that it does not open HTTP or SQL. `game_runtime/README.md` says the empty directories beside `session.py` (`core`, `movement`, `combat`, `physics`, `vehicles`, and the rest) are reserved names. They are not a second engine.

`app/core/config.py` sets `game_tick_rate` to 20. `app/main.py` constructs `TickManager` with that rate. `app/game/tick_manager.py` sleeps until the next interval and calls the update with `1 / tick_rate` seconds. The callback in `app/main.py` calls `game_engine.step`, publishes snapshots, then drains `take_results()`.

| System | Where the server decides it |
| --- | --- |
| Movement | `simulate.py` `_move` scales the input vector to length 1, uses `MatchRules.speed` on foot, and clamps the point to the map square. |
| Collision | `app/game/collision.py` `slide` rejects a destination inside a match `Blocker`. `_move` applies that result. |
| Hits | `simulate.py` `_shoot` accepts a target in front of the aim, inside weapon range, and within `hit_radius`. |
| Ammo | `_shoot` decrements `mag`. `_start_reload` and `_finish_reload` move `light` or `medium` from the inventory into the magazine. |
| Healing | `_use_item` spends a `bandage` or `medkit` from `app/game/items.py` `HEALS` and raises health, capped at 100. |
| Loot | `_pickup` copies a nearby `LootNode` into the live inventory and marks the node taken. |
| Buggy | `_spawn_vehicles` places `kind="buggy"`. `_board` and `_exit_vehicle` set the occupant. `_move` uses `VEHICLES["buggy"]["speed"]` while seated. `_shoot` refuses fire from a vehicle. |
| Zone damage | `_apply_zone` subtracts `zone_dps` per second from a living player outside the circle, then eliminates at health 0 with cause `zone`. |
| Elimination | `_eliminate` sets status `eliminated`, health 0, and appends the elimination order. |
| Match results | `_record_results` appends `MatchResult` (kills, win, placement) to `pending_results`. `GameEngine.take_results` returns that list and clears it. |

Weapon, heal, and buggy numbers live in `app/game/items.py`. Speeds, zone radii, and `hit_radius` live in `app/game/rules.py`. `app/game/state.py` `VehicleNode` stores id, kind, position, and occupant. It has no fuel field and no vehicle-health field.

## Client and control plane

The client sends intent. `app/networking/protocol.py` accepts `player.input` (`move_x`, `move_y`, `aim_x`, `aim_y`) and `player.action` (`shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`, `board`, `exit`). `app/networking/websocket.py` turns those messages into `GameEngine.set_input` and `GameEngine.perform`. There is no damage field and no position field on those payloads. `tests/unit/test_runtime_session.py` calls `perform` with action `damage` and the health of the other player stays unchanged.

FastAPI remains the control plane: accounts, sessions, durable lobbies, catalogs, map publishing, and the WebSocket route. The tick callback does not query SQL. `simulate.py` has no database import. After `step` returns, `app/main.py` drains finished results and `app/services/persistence_service.py` writes kills, wins, and matches played. High-frequency state stays in memory: positions, health, aim, magazines, loot nodes, vehicles, and blockers on `WorldState`.

`docs/NETWORK_PROTOCOL.md` is version 1 JSON over HTTP and WebSocket. This page assigns no numeric opcodes.

## Clients

`com.ros.client` is the independent client. It is the application that calls this server's JSON. Package `com.netease.chiji` is not a client of this server. The original APK and original Rules of Survival numbers stay out of scope. Evidence for that boundary is `docs/CUSTOM_SERVER_ARCHITECTURE.md` and `docs/COMPATIBILITY.md`.

## Engine choice

No replacement engine is selected. Godot, Unity, Unreal, C++, and Rust are unevaluated options. The runtime that executes today is the Python loop in `app/game`. `docs/ENGINE_EVALUATION.md` compares those options and keeps this loop for the first two-client playable test. ADR-0010 records that working runtime. It does not add another engine.

## Still missing

These items are absent from the files read for this audit:

- A separate operating-system process for the tick. FastAPI and `TickManager` share one process (`app/main.py`, ADR-0010).
- Client-side prediction and interpolation. `docs/GAME_RUNTIME.md` records both as unimplemented.
- UDP. The live transport is WebSocket text frames in `docs/NETWORK_PROTOCOL.md`.
- Armor, hit locations, crouch, and prone. `PlayerAction` has no crouch or prone. `items.py` has no armor table. `docs/GAMEPLAY_SYSTEMS.md` lists the same gaps.
- Team revive and spectating. Lobby teams are durable HTTP rows. The live match has no revive action and no spectate message.
- Vehicle fuel and vehicle health. `VehicleNode` does not store them.
- Loading collision from a published map. Match blockers are in-memory rectangles. `docs/GAME_RUNTIME_MIGRATION.md` says the tick does not copy `map_objects` into `Match.blockers`.
- Versioned gameplay-config releases (`draft`, `validate`, `approve`, `publish`). Map packages have their own draft and publish flow. `MatchRules` is a Python object the match keeps from start. There is no gameplay-config release table.
- An admin console that edits live rules. Map publishing is a username allow-list on `app/api/v1/admin_maps.py`. It does not change the running `MatchRules`.

## First milestone

The brief's first milestone is two clients, auth, spawn, move, collide, shoot, damage, death, and a persisted result.

| Step | Already implemented | Evidence | Not done |
| --- | --- | --- | --- |
| Two clients | Two player ids share one in-memory world. Two WebSocket test clients can authenticate. | `game_runtime/session.py` `AuthoritativeSession.start`; `tests/unit/test_runtime_session.py`; `tests/integration/test_websocket_reliability.py` `test_two_clients_send_input_and_a_shot_is_rejected_outside_a_match` | A two-device run of `com.ros.client` through a full match has not been done. `docs/COMPATIBILITY.md` records HTTP checks only for that app. |
| Auth | HTTP bearer login and WebSocket `auth` exist on the control plane. | `app/networking/protocol.py`; `app/networking/websocket.py`; `tests/integration/test_websocket_reliability.py` | `AuthoritativeSession` calls `GameEngine` directly and does not present a token. |
| Spawn | A match start places players, then lands them when `playing` begins. `drop_time` of 0 lands them on the first step. | `simulate.py` `_create_match`, `_enter_playing`, `_land`; `AuthoritativeSession.start` requires phase `playing` | A device has not shown that spawn. |
| Move | The tick integrates `player.input` at `MatchRules.speed`. | `tests/unit/test_simulation.py` `test_on_foot_movement_uses_the_server_speed`; `simulate.py` `_move` | A device has not shown that move. |
| Collide | A blocker stops a forward step. | `tests/unit/test_runtime_session.py` `test_a_blocker_stops_forward_movement`; `collision.py` `slide` | A device has not shown that collision. Published map collision is still unloaded. |
| Shoot | `fire` calls `perform(..., "shoot", ...)`. | `game_runtime/session.py` `AuthoritativeSession.fire`; `simulate.py` `_shoot` | A device has not shown that shot. |
| Damage | The weapon table subtracts health. A client action named `damage` is rejected. | `items.py` `WEAPONS`; `tests/unit/test_runtime_session.py` `test_a_client_cannot_report_its_own_hit`; `tests/unit/test_simulation.py` `test_results_record_placement_and_kills_only` | A device has not shown that damage. |
| Death | Health at 0 sets `eliminated`, ends the match, and names the winner. | `simulate.py` `_eliminate`, `_maybe_finish`; `tests/compatibility/gameplay/test_scenario.py` (steps `simulate_elimination` and `end_match` in `tools/game_simulator/runner.py`) | A device has not shown that death. |
| Persist result | The tick drains in-memory `MatchResult` rows. The scenario labels the in-memory total copy `persist_results`. The process writes kills, wins, and matches played only after the tick. | `GameEngine.take_results`; `tests/unit/test_runtime_session.py` `test_the_server_applies_damage_and_records_the_winner`; `tests/unit/test_simulation.py` `test_results_record_placement_and_kills_only`; `app/main.py` then `persistence_service.save_player_progress` | The named unit tests do not open SQL. A two-client device run has not confirmed a durable row. |

On 2026-11-11, `pytest tests/unit/test_runtime_session.py tests/unit/test_simulation.py tests/compatibility/gameplay -q --tb=line` reported `9 passed`. That run did not start Docker, did not open `ros_server.db`, and did not exercise two physical devices.

On 2026-11-11, `pytest tests/integration/test_two_client_match.py -q --tb=short` reported `1 passed` in 5.95s. Two authenticated WebSocket clients joined one live match, moved inside the map, stopped against a blocker, and one shot eliminated the other. The server applied pistol damage and magazine use. `GET /api/v1/players/me` then showed the winner's kill, win, and match, and the other player's match. The test shortened queue, countdown, drop, and bot fill on the running engine so the tick could finish without bots. Speed, damage, zone, and vehicle numbers were unchanged. That run did not start Docker, did not open `ros_server.db`, and a two-device run was not done.

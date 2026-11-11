# ADR-0010 — The Python match loop stays authoritative

- Decision ID: ADR-0010
- Date: 2026-11-11
- Status: accepted

## Context

`app/game` already simulates movement, weapons, damage, elimination, zone, loot, and vehicles in memory. `TickManager` calls that loop at `game_tick_rate` (20). `simulate` does not import SQLAlchemy. Match results are copied out after the tick and then written by `persistence_service`. WebSocket clients send `player.input` and `player.action`. They do not send damage or a new position.

## Problem

A battle-royale server needs one owner of gameplay truth. Replacing the loop with Godot, Unity, Unreal, C++, or Rust, or moving every rule into a FastAPI handler, would discard the tested simulation or put it on the request path.

## Options considered

- Adopt a dedicated Godot, Unity, or Unreal server as the simulation.
- Rewrite the simulation in C++ or Rust.
- Keep the Python loop as the authority and add a headless session in front of it.

## Chosen solution

Keep the Python loop. `game_runtime.AuthoritativeSession` starts that loop for a two-player world. FastAPI remains the control plane: login, sessions, lobby rows, map catalog, and the WebSocket that feeds the same engine. Environment blockers live on the in-memory match and are applied inside `_move`.

## Reason

The tick is already fixed-step and free of database calls. ADR-0001 keeps one process until a later decision splits it. The weapon and movement numbers are this server's rules, not original Rules of Survival data.

## Consequences

HTTP and the tick share a process and the GIL. A slow request can delay a tick. A separate process, a UDP transport, and a different simulation engine each need a new decision. Client prediction is not part of this decision. A running match keeps the `MatchRules` instance it started with.

## Related tasks

None in the task registry. The milestone record is `reports/game-runtime/RUNTIME_MILESTONE.md`.

## Related changes

`app/game/collision.py`, `game_runtime/session.py`

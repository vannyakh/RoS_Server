# Authoritative runtime milestone

The gameplay authority remains the Python loop in `app/game`. `game_runtime.AuthoritativeSession` starts a two-player world on that loop. FastAPI is the control plane. No Godot, Unity, Unreal, C++, or Rust runtime was added. ADR-0010 records that choice.

## What a client can do

1. `AuthoritativeSession.start` connects two players and reaches `playing`.
2. `command` stores movement. The tick applies speed 5 and map bounds.
3. A match `Blocker` stops a destination that lands inside it. The player slides along the free axis.
4. `fire` uses the server pistol: magazine, cooldown, aim, and 22 damage. The action name `damage` is rejected and health does not change.
5. The fifth hit eliminates the other player. `results` returns a win for the shooter and a loss for the target.
6. Two WebSocket clients authenticate with the existing login token. One movement input is acknowledged with a tick. A shot before joining a match returns `Not in a match`.

Positions are not accepted from the client. The input payload has no position field.

## Tests

`pytest tests/unit/test_runtime_session.py tests/unit/test_gameplay.py tests/compatibility/weapons/test_shot.py tests/compatibility/gameplay/test_scenario.py tests/integration/test_websocket_reliability.py`

Result: `16 passed` for that selection. The full suite is `98 passed, 1 skipped`. The skip is the existing PostgreSQL test.

The deterministic scenario still passes, so an empty blocker list leaves the previous movement result in place.

## Tick cost

`python -m game_runtime.benchmark` on this machine:

`ticks=600 players=2 elapsed_s=0.014833 mean_ms=0.0247`

That is the simulation call only, at a 20 Hz step, for two players. It is not a capacity test and it does not include HTTP, snapshots over a socket, or a filled battle-royale match.

## Still open

- The tick and FastAPI share one process.
- Blockers are points, not swept volumes. A step longer than a thin wall can pass through it.
- Map packages are not loaded into the live match.
- Team revive, client prediction, UDP, and versioned gameplay configuration are not implemented.
- The admin console does not edit these rules yet. A match keeps the `MatchRules` it started with.
- Original Rules of Survival combat values remain `unknown` in the compatibility matrix.

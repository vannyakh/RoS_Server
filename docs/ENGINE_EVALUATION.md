# Engine evaluation

Audit date: 2026-11-11. This page compares runtimes for the simulation. It does not start a Godot, Unity, Unreal, C++, or Rust project. The current choice, until a later architecture decision, is the Python loop in `app/game`.

`docs/SIMULATION_ENGINE_EVALUATION.md` and ADR-0010 already keep that loop. This page adds the criteria below. Android rendering stays a separate choice and is not decided here.

| Option | What already exists | Process isolation | Tick cost | Solo team | What would be thrown away |
| --- | --- | --- | --- | --- | --- |
| Keep the current Python loop | `app/game` (`simulate.py`, `rules.py`, `items.py`, `state.py`, `collision.py`, `engine.py`, `tick_manager.py`), `game_runtime/session.py`, WebSocket `player.input` and `player.action`, and the tests named in `docs/AUTHORITATIVE_RUNTIME.md`. Default rate is 20 Hz in `app/core/config.py`. | The tick and FastAPI share one process. `simulate` does not query SQL. Results are drained after `step` in `app/main.py`. A second OS process is not built. | A prior local benchmark in `reports/game-runtime/RUNTIME_MILESTONE.md` measured the simulation call only: 600 ticks, 2 players, mean about 0.025 ms. This audit did not re-run that benchmark. It is not a capacity test. | One Python process and the existing pytest suite. | Nothing in the current simulation. Empty `game_runtime/` folders stay reserved names (`game_runtime/README.md`). |
| Godot | No Godot project, scene, or headless export in this repository. | A headless export could be another OS process. None is running. | Not measured. | A second editor, export, and language for one person, beside the Python tests. | The tested rules in `app/game` would be rewritten, or kept as a second source of truth. |
| Unity | No Unity project or dedicated-server build in this repository. | A dedicated-server player could be another OS process. None is running. | Not measured. | A second editor and a license check before any ship, for one person. | The same rewrite of `app/game` and its tests. |
| Unreal | No Unreal project or server target in this repository. | A dedicated server could be another OS process. None is running. | Not measured. | The largest extra runtime for one person. | The same rewrite, with the least overlap with the current pytest suite. |
| C++ | No C++ simulation sources in this repository. | A native process could own the tick. None is running. | Not measured. | A new build, bindings, and tests before the two-client playable test. | The Python loop the current tests already cover. |
| Rust | No Rust simulation crate in this repository. | A native process could own the tick. None is running. | Not measured. | A new crate and a new way to reach the existing JSON contract. | The Python loop the current tests already cover. |

## Recommendation

Keep `app/game` for the first two-client playable test. `game_runtime.AuthoritativeSession` is the headless wrapper over `GameEngine`. FastAPI stays the control plane.

Do not start a Godot, Unity, Unreal, C++, or Rust project for that test. Adopting one of those later requires a new architecture decision, with the same client messages (`player.input`, `player.action`, and the `state` snapshot) and a test that replaces the Python evidence. This page does not make that decision.

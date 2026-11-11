# Simulation engine evaluation

The simulation choice and the Android rendering choice are separate. This note decides the simulation for the current milestone. It does not add Godot, Unity, Unreal, C++, or Rust to the repository.

| Runtime | Fit for this repository | Cost of adopting it now |
| --- | --- | --- |
| Current Python `app/game` | The 20 Hz loop, weapon checks, results, and WebSocket input already live here and have tests. | Stays in one process. A heavy HTTP request can delay a tick. |
| Godot dedicated server | One editor can own 3D collision and a headless export. | The tested Python rules would have to be reimplemented, and the export would be a second build. |
| Unity dedicated server | Strong multiplayer samples and a dedicated-server build. | Same rewrite, plus a commercial license check before shipping. |
| Unreal dedicated server | High-end shooter simulation and replication. | Largest runtime and the weakest match to the current Python tests. |
| C++ | Full control of tick time and memory. | A new codebase beside the one the tests already cover. |
| Rust | The same control with a stronger memory model. | A new codebase and a new network stack before the current two-player rules are finished. |

## Decision

Keep the Python simulation as the authority. FastAPI stays the control plane for accounts, sessions, durable lobbies, map packages, and configuration. `game_runtime` calls `GameEngine`; it does not embed another engine.

A later replacement can consume the same client messages: `player.input`, `player.action`, and the `state` snapshot. That replacement needs its own ADR. The map manifest stays `local_xyz_y_up_meters` and `portable_gltf`, so the rendering engine can change without a database migration.

Android rendering is still open. The comparison for Godot, Unity, Unreal, and LibGDX is in the client document `docs/MAP_ENGINE_EVALUATION.md`. The Compose client remains the input and preview shell until a renderer is chosen.

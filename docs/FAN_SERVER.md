# Fan server

This repository is a fan-made independent game server. It is not an official Rules of Survival service. It is not a license to redistribute publisher assets, artwork, sounds, or game binaries.

The running server is one Python FastAPI process. Routes, frames, and match numbers below are this project's design. Original client behavior stays unknown.

## What the process does today

- **Control plane.** HTTP registers an account, logs it in, and returns the profile. The route list is `docs/API_CONTRACT.md`.
- **Wallet.** A new profile starts with coin, diamond, and an equipped skin. The catalog is the one in `app/services/cosmetics_service.py`.
- **Lobby.** An authenticated player can create a durable lobby, join it, and set ready. That room is a database row. The in-memory matchmaking queue is a separate step on the socket.
- **Live match.** The same process runs the simulation at 20 Hz. After the version-1 JSON `auth` frame, `lobby.join` enters the queue, and the tick pushes `state` snapshots. Frame rules are `docs/NETWORK_PROTOCOL.md`. Movement, weapons, and the zone are `docs/GAMEPLAY_SYSTEMS.md`.

## Explicitly absent

- The original Android and iOS clients are not clients of this server. This server does not speak their protocol and does not pass their patch gate.
- There is no role-based admin console.
- The match loop is not a separate runtime process.
- Finishing a match does not pay coin or diamond.

Original opcodes, weapon statistics, and rewards are not implemented here.

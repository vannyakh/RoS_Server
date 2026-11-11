# Connection lifecycle

Date: 2026-11-11. P0 covers startup, server discovery, authentication, and lobby. The original client and this server do not share a lifecycle.

## Original client

| Step | Status | Record |
| --- | --- | --- |
| Process start | CONFIRMED | Activity `com.netease.neox.Client` opened on LDPlayer |
| Patch gate | CONFIRMED | The surface stayed on the text "Retrieving patch lists 0.00%" |
| Patch-list request and response bytes | UNKNOWN | The exchange was not captured. The format is not specified |
| Server discovery | UNKNOWN | No hostname from the client is written here as an endpoint to implement |
| Authentication | UNKNOWN | The login screen was not reached |
| Lobby | UNKNOWN | The lobby was not reached |
| Later match socket | UNKNOWN | No gameplay connection was observed |
| Using this server's HTTP or WebSocket lifecycle | NOT_SUPPORTED | No field from the native client has been shown to match this API |

Sibling `research/MULTIPLAYER_RESEARCH.md` records the same stop. `docs/reverse-engineering/CLIENT_ANALYSIS.md` records the same stop and states that a public search was not used as a packet source.

Clearing the patch gate by bypassing authentication, encryption, certificate pinning, anti-cheat, or access controls is out of scope. The next lifecycle to exercise is the independent client's, below.

## This server

DOCUMENTED in `docs/NETWORK_PROTOCOL.md` and CONFIRMED by the message models in `app/networking/protocol.py`.

1. The operator supplies the base URL. Development uses a loopback address with `adb reverse`, as written in `docs/ARCHITECTURE.md`. That practice is this project's development setup. It is NOT_SUPPORTED as discovery for the original APK.
2. `POST /api/v1/auth/login` returns a bearer token. Later HTTP calls send `Authorization: Bearer`.
3. The WebSocket at `/api/v1/ws` accepts `auth` as the first JSON payload. The token is inside the payload.
4. Durable lobby membership uses HTTP and the player id from `GET /api/v1/players/me`.
5. `lobby.join` and `lobby.leave` change the in-memory queue. They do not create the durable lobby row.

Each of those steps is CONFIRMED as this project's design and NOT_SUPPORTED for package `com.netease.chiji`.

Sibling `research/MULTIPLAYER_RESEARCH.md` records that `com.ros.client` completed health, invalid login, and profile calls. Lobby create, lobby join, and the live socket were not part of that completed check. Those three calls remain DOCUMENTED in the API contract and are the next lifecycle to run, with two independent sessions.

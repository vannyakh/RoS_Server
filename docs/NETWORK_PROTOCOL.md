# Network protocol

This is the wire protocol implemented by this server and used by the independent Android client. It is version 1 JSON over HTTP and WebSocket. It is not an original Rules of Survival or NetEase client protocol.

Original-client research stays in `docs/reverse-engineering/`. Those notes are not opcodes, encryption rules, or a patch-list format for this server. This document does not assign numeric opcodes.

HTTP paths, bodies, and status codes are listed in `docs/API_CONTRACT.md`. This page is the session and realtime contract.

## Transport

| Channel | Address | Encoding |
| --- | --- | --- |
| Control plane | `http://<host>:8000` | JSON |
| Live session | `ws://<host>:8000/api/v1/ws` | One JSON object per text frame |

Development on an Android emulator uses `127.0.0.1:8000` with `adb reverse tcp:8000 tcp:8000`. A physical device supplies its own base URL at runtime. Release traffic is HTTPS and `wss`.

Frames larger than 4096 bytes are rejected. The client waits at most 5 seconds for the first frame. An idle socket closes after 15 seconds.

## Envelope

Every WebSocket message uses the same object:

```json
{"version":1,"type":"<name>","sequence":0,"payload":{}}
```

`version` is `1`. Any other version is rejected. `sequence` is a non-negative integer. After `auth`, each client sequence must be greater than the previous accepted sequence. More than 20 client messages in one second return `error` with detail `Rate limit exceeded`.

## Session

1. `POST /api/v1/auth/login` returns `access_token`, `token_type` (`bearer`), and `expires_in` seconds.
2. Later HTTP calls send `Authorization: Bearer <access_token>`.
3. The socket sends `auth` first. The token is inside `payload`. It is not placed in the URL.

```json
{"version":1,"type":"auth","sequence":0,"payload":{"token":"<access_token>"}}
```

Success:

```json
{"version":1,"type":"auth.ok","sequence":0,"payload":{"player_id":"<account id>"}}
```

`player_id` in `auth.ok` is the account id. Durable lobby, inventory, and stored-match calls use the player id from `GET /api/v1/players/me`.

The server accepts the socket only when the JWT is valid and the stored session hash is present, unrevoked, and unexpired. Logout revokes that hash only.

| Failure | Result |
| --- | --- |
| First frame is not `auth` | `error`, then close `4003` |
| Malformed JSON | `error`, then close `4002` |
| No frame within 5 seconds | close `4001` |
| Invalid, expired, or revoked token | `error` with `Invalid or expired token`, then close `4003` |
| Frame over 4096 bytes | close `1009` |
| Idle for 15 seconds | close `4004` |
| A second socket for the same account | the previous socket closes with `4000` |

## Client messages

| type | payload | Server reply |
| --- | --- | --- |
| `heartbeat` | `{}` | `heartbeat` with an empty payload |
| `player.input` | `move_x`, `move_y`, `aim_x`, `aim_y`, each from -1 to 1 | `player.input.ack` with `tick` |
| `player.action` | `action`, optional `loot_id`, optional `item_id` | `player.action.ack` with `ok` and `detail` |
| `lobby.join` | `{}` | `lobby.join.ack` with `ok` and `detail` |
| `lobby.leave` | `{}` | `lobby.leave.ack` with `ok` and `detail` |
| `match.forfeit` | `{}` | `match.forfeit.ack` with `ok` and `detail` |

`action` is one of `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`, `board`, `exit`.

`lobby.join` and `lobby.leave` change the in-memory queue. They do not create or leave a durable lobby row. Durable rooms use the HTTP routes in `docs/API_CONTRACT.md`.

## Server push

The 20 Hz tick sends one snapshot to the current socket:

```json
{"version":1,"type":"state","sequence":<tick>,"payload":{}}
```

The payload includes `player_id`, `tick`, `x`, `y`, `z`, `health`, `status`, `match_id`, `aim_x`, `aim_y`, `kills`, `map_size`, and `vehicle`. During a match it also includes `match`. `sequence` on `state` is the tick, not the client's sequence.

Errors that leave the socket open use:

```json
{"version":1,"type":"error","sequence":<client sequence>,"payload":{"detail":"<message>"}}
```

## Identity of this protocol

The names above are the literals in `app/networking/protocol.py`. Tests may require the documentation to match that file. A passing test shows this server agrees with itself.

The original game client uses a different interface. This server does not implement that interface, its update exchange, or its client protections.

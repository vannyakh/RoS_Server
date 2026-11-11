# Runtime message contract

This is the live WebSocket contract in `app/networking/protocol.py` and `app/networking/websocket.py`. It is not an original Rules of Survival protocol.

The client authenticates with the account token from `POST /api/v1/auth/login`. The first socket message is `auth`. `auth.ok` returns the account id as `player_id`.

Later messages use version 1 and an increasing `sequence`.

## Client to server

`player.input`

```json
{"version":1,"type":"player.input","sequence":2,"payload":{"move_x":1,"move_y":0,"aim_x":1,"aim_y":0}}
```

`move_x`, `move_y`, `aim_x`, and `aim_y` are each from -1 to 1. The server stores the input and moves the pawn on the next tick at `MatchRules.speed`. The ack is `player.input.ack` with the current tick. The payload has no position field. A client position would be ignored because the parser does not accept one.

`player.action`

```json
{"version":1,"type":"player.action","sequence":3,"payload":{"action":"shoot"}}
```

`action` is one of `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`, `board`, `exit`. There is no `damage`, `ammo`, or `health` field. `shoot` checks the server weapon, magazine, cooldown, reload, and aim, then subtracts the server damage. The ack is `player.action.ack` with `ok` and `detail`. Outside a match the detail is `Not in a match`.

`lobby.join` and `lobby.leave` join the in-memory queue. They do not create a durable lobby row.

## Server to client

`state` carries the pawn the server simulated: position, health, status, aim, kills, map size, vehicle, and a match object while the player is in one. The client renders that snapshot. It does not vote on the winner.

When the match ends, `GameEngine.take_results()` returns `player_id`, `kills`, `win`, and `placement`. The process that owns the tick persists kills and the win after the step. The tick function itself does not open a database session.

## Versioning

Message `version` is 1. A running `GameEngine` keeps the `MatchRules` it was constructed with. Publishing a new gameplay configuration must start a new match. It must not rewrite the rules of a match that is already in `playing`.

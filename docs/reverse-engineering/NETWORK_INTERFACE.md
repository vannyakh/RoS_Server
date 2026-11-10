# Network interface

This page describes this server's JSON protocol. It is not an official Rules of Survival client protocol. ADR-0001 records that boundary.

## Requirements

- The WebSocket path is `/api/v1/ws`.
- The first message is version 1, type `auth`, and the token is inside `payload`. The token is not placed in the URL.
- The server answers `auth.ok` before the connection is treated as authenticated.
- An invalid, expired, or revoked token is rejected. Logout revokes only the presented session.
- State snapshots are sent by the server tick. The default tick is 20 Hz.
- `board` and `exit` are local vehicle actions. They are not original client packets.

## Message types

- `auth`
- `heartbeat`
- `player.input`
- `player.action`
- `lobby.join`
- `lobby.leave`
- `match.forfeit`

## Player actions

- `shoot`
- `reload`
- `pickup`
- `use`
- `equip`
- `jump`
- `discard`
- `board`
- `exit`

OBSERVED FACT: These names are the `Literal` values in `app/networking/protocol.py`.

INTERPRETATION: Protocol tests may require this list. A passing test shows the documentation matches this server.

HYPOTHESIS: The original client uses a different interface. That interface is not documented here.

IMPLEMENTATION IMPACT: Do not add an official packet format from community posts. Unknown message types and version values other than 1 stay rejected.

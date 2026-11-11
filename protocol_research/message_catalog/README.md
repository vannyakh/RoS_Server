# Message catalog

Date: 2026-11-11. This catalog lists names that exist in this repository. It does not assign numeric opcodes. Example opcode numbers are not a specification, and none are introduced here.

## Original client

| Catalog item | Status |
| --- | --- |
| Startup observed through the patch-gate text | CONFIRMED |
| Patch-list message layout | UNKNOWN |
| Encryption and certificate handling as a wire format | UNKNOWN |
| Authentication messages | UNKNOWN |
| Lobby messages | UNKNOWN |
| Matchmaking, gameplay, and result messages | UNKNOWN |
| Admin messages | UNKNOWN |
| Any original opcode, header, or field | UNKNOWN |
| Compatibility of those unknown messages with this server | NOT_SUPPORTED |

`assets/protocol_data` was listed by name in the sibling asset inventory and was not opened. Its contents stay UNKNOWN. A filename is not a field list.

Public pages cited from `docs/reverse-engineering/CLIENT_ANALYSIS.md` contributed no packet fields to this catalog. DIS-0011 and DIS-0012 in `docs/reverse-engineering/RESEARCH_INDEX.md` record that boundary.

## This server

CONFIRMED. `ClientMessage.type` in `app/networking/protocol.py` is exactly:

| type | Direction | Role |
| --- | --- | --- |
| `auth` | Client to server | First frame. Token in `payload` |
| `heartbeat` | Client to server | Keepalive |
| `player.input` | Client to server | Move and aim |
| `player.action` | Client to server | `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`, `board`, `exit` |
| `lobby.join` | Client to server | Enter the in-memory queue |
| `lobby.leave` | Client to server | Leave that queue |
| `match.forfeit` | Client to server | Leave the live match |

The envelope is `version` 1, `type`, `sequence`, and `payload`. Server replies and the `state` snapshot are DOCUMENTED in `docs/NETWORK_PROTOCOL.md` and `docs/reverse-engineering/NETWORK_INTERFACE.md`. HTTP bodies are DOCUMENTED in `docs/API_CONTRACT.md`.

Wallet messages are HTTP, not a second socket catalog. The independent prices are CONFIRMED in `app/services/cosmetics_service.py` and summarized in `docs/GAME_RULES.md`.

These names are this project's design. They are NOT_SUPPORTED as the original APK's catalog. Adding a type requires the model, the handler, and a test in the same change. Research notes do not add one.

# Protocol research notes

Date: 2026-11-11. These folders hold evidence notes. They do not hold executable protocol code, generated parsers, or a stand-in for the original client's update gate.

The narrative index is `docs/PROTOCOL_RESEARCH.md`. The compatibility conclusion is `docs/COMPATIBILITY.md`: the original package `com.netease.chiji` is not a client of this server.

## Status labels

CONFIRMED, DOCUMENTED, INFERRED, UNKNOWN, NOT_SUPPORTED.

Definitions are in `docs/PROTOCOL_RESEARCH.md`.

## Folders

| Path | Research order | What the note covers |
| --- | --- | --- |
| `protocol_research/client_inventory/README.md` | P0 startup | Package identity and files that stayed unread |
| `protocol_research/connection_lifecycle/README.md` | P0 | Patch gate, discovery, authentication, lobby |
| `protocol_research/message_catalog/README.md` | P0 and P1 | This server's JSON names, and the empty original catalog |
| `protocol_research/compatibility_matrix/README.md` | P0 through P2 | NOT_SUPPORTED original client, UNKNOWN original balance values |
| `protocol_research/evidence/README.md` | All | Sources, including the public-source page that copied no packet fields |

## Boundary

Original opcodes, encryption, patch-list bytes, and discovery hosts are UNKNOWN. None of those unknowns is filled with an example number or a hostname from the client. The running simulation remains `app/game`.

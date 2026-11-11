# Protocol research

Date: 2026-11-11. This page records what was observed about the original Android client and what this server actually implements. It is an evidence index. It is not an original Rules of Survival packet specification.

The wire format this process speaks is version 1 JSON, written in `docs/NETWORK_PROTOCOL.md` and `docs/API_CONTRACT.md`, with message names in `app/networking/protocol.py`. Research notes do not add opcodes, headers, or fields to that contract.

## Status labels

| Status | Use |
| --- | --- |
| CONFIRMED | Seen in a permitted file, a recorded run, or this repository's code |
| DOCUMENTED | Written in an accepted page of this project as its own design |
| INFERRED | A reading that follows from a confirmed observation and does not name a protocol field |
| UNKNOWN | Not observed. Left empty on purpose |
| NOT_SUPPORTED | The original package is not a client of this server for that capability |

`docs/RESEARCH_POLICY.md` uses the first, third, and fourth labels. DOCUMENTED and NOT_SUPPORTED are added here so a project design and an unsupported original client stay distinct.

## Subjects

| Subject | Identity | Role |
| --- | --- | --- |
| Original Android client | Package `com.netease.chiji`, versionName `1.610637.617289`, versionCode `1227927`, NetEase NeoX, native library `libclient.so` | Read-only research reference in the sibling client repository |
| This server | FastAPI process in this repository | Custom server. Control plane plus the in-process loop in `app/game` |
| Independent Android app | `Android_API_Client`, package `com.ros.client` | Separate application. It is the client that calls this server's JSON API |
| Admin tree | Sibling admin repository | Documentation only. No admin application is built |

Public web sources already recorded in `docs/reverse-engineering/CLIENT_ANALYSIS.md` were not used as packet fields. No APK was downloaded for this page. `assets/protocol_data` was not opened. `libclient.so` was not disassembled.

## Research order

| Order | Topic | Original client | This server |
| --- | --- | --- | --- |
| P0 | Startup | CONFIRMED. On LDPlayer the activity `com.netease.neox.Client` stayed on the on-screen text "Retrieving patch lists 0.00%". | CONFIRMED. One FastAPI process serves HTTP and WebSocket and starts the loop in `app/game`. |
| P0 | Server discovery | UNKNOWN as a protocol. No discovery host is recorded here as an endpoint to implement. | DOCUMENTED. Operators supply the base URL. Development notes in `docs/ARCHITECTURE.md` use a loopback address with `adb reverse`. NOT_SUPPORTED for the original APK. |
| P0 | Authentication | UNKNOWN. Login was not reached. | CONFIRMED. HTTP bearer tokens and WebSocket `auth` check a JWT and a stored session hash. DOCUMENTED in `docs/NETWORK_PROTOCOL.md`. NOT_SUPPORTED for the original APK. |
| P0 | Lobby | UNKNOWN. The lobby was not reached. | CONFIRMED. Durable rooms are HTTP routes. `lobby.join` and `lobby.leave` change the in-memory queue. NOT_SUPPORTED for the original APK. |
| P1 | Matchmaking | UNKNOWN. No match socket was captured. | CONFIRMED. The queue in `app/game` waits or fills, then starts a match. NOT_SUPPORTED for the original APK. |
| P1 | Gameplay | UNKNOWN. No shot, movement, or zone was observed on the original client. | CONFIRMED. Independent rules run in `app/game` and are summarized in `docs/GAME_RULES.md`. NOT_SUPPORTED for the original APK. |
| P1 | Match results | UNKNOWN. | CONFIRMED. Finished human results store kills, win, and placement. Experience and currency rewards from the match are not granted. NOT_SUPPORTED for the original APK. |
| P2 | Updates | CONFIRMED that the client displayed patch-list progress and stopped. The patch-list format is UNKNOWN. | This server does not implement that update exchange. NOT_SUPPORTED. |
| P2 | Admin | UNKNOWN. | DOCUMENTED. Map publishing is a username allow-list on this server's map routes. The sibling admin repository has no application. NOT_SUPPORTED as an original admin protocol. |

## Readings that stay short of a protocol

| Reading | Status | Why |
| --- | --- | --- |
| The launched original surface is the NeoX activity, and the classified Android layouts are account-SDK chrome | INFERRED for where gameplay UI lives. CONFIRMED for the activity that was on screen | Sibling `research/CLIENT_ARCHITECTURE.md` |
| Filename groups among the other native libraries suggest audio, video, crash, and account-SDK helpers | INFERRED | Names only. Internal behavior is UNKNOWN |
| The original client speaks this server's JSON | NOT_SUPPORTED | No original login, lobby, or match message was captured, and no field from the native client has been shown to match `/api/v1` or `/api/v1/ws` |
| Original opcodes, encryption, handshake, and patch-list bytes | UNKNOWN | They were not captured and are not specified in this repository |

## Where the notes live

| Path | Contents |
| --- | --- |
| `protocol_research/README.md` | Folder index |
| `protocol_research/client_inventory/README.md` | Package identity and what was left unread |
| `protocol_research/connection_lifecycle/README.md` | P0 startup through lobby |
| `protocol_research/message_catalog/README.md` | This server's message names, and the empty original catalog |
| `protocol_research/compatibility_matrix/README.md` | Unsupported original client versus unknown original balance values |
| `protocol_research/evidence/README.md` | Sources and the work that was not done |
| `docs/COMPATIBILITY.md` | Compatibility conclusion |
| `docs/CUSTOM_SERVER_ARCHITECTURE.md` | Shape of the custom server |
| `docs/GAME_RULES.md` | Independent numbers, with original values left UNKNOWN |

## Next step

Keep the original package read-only at the patch gate. The useful next check is two `com.ros.client` sessions on this server's existing login, lobby, and match loop. That check does not need a patch-list stand-in, a disassembly of `libclient.so`, or an opened `assets/protocol_data` tree.

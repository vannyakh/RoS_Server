# Compatibility

Date: 2026-11-11. Compatibility here answers two different questions. They stay in separate rows.

## Conclusion

The original Android client, package `com.netease.chiji` versionName `1.610637.617289`, is not a client of this server. That outcome is NOT_SUPPORTED. The independent client is `Android_API_Client`, package `com.ros.client`, which calls this server's version 1 JSON.

Original combat, movement, weapon, zone, and reward values remain UNKNOWN. A test that matches `app/game` shows this server agrees with itself. `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` keeps every original-behavior row at `unknown` for that reason. This page does not change those rows.

## Two questions

| Question | Result | Status |
| --- | --- | --- |
| Can the original APK log in, join a lobby, or play a match on this process? | No supported path. Startup stopped at the patch-gate text. Login and lobby were not reached. No original message was shown to match `/api/v1` or `/api/v1/ws`. | NOT_SUPPORTED |
| Do this server's rule numbers match original Rules of Survival? | No authorized original specification was compared. The matrix records 0 compatible and 43 unknown. | UNKNOWN |
| Does `com.ros.client` use this server's JSON? | The sibling research records health, invalid login, and profile calls. Live lobby join and the match socket were not part of that completed check. | CONFIRMED for those HTTP checks. The live match path is DOCUMENTED in `docs/NETWORK_PROTOCOL.md` and still needs a two-client run |
| Does the browser page at `/play` speak this JSON when `assets/play` is present? | It is a client of this server when that static tree exists. It is not the original mobile client. | DOCUMENTED in `docs/ARCHITECTURE.md` and `docs/reverse-engineering/CLIENT_ANALYSIS.md` |

## Original client, by research order

| Order | Topic | Status | Evidence |
| --- | --- | --- | --- |
| P0 | Startup through the patch gate | CONFIRMED | On-screen text "Retrieving patch lists 0.00%". Sibling `research/CLIENT_ARCHITECTURE.md` and `docs/reverse-engineering/CLIENT_ANALYSIS.md` |
| P0 | Server discovery as a protocol | UNKNOWN | No host from the client is copied here as an endpoint |
| P0 | Authentication and lobby on the original client | UNKNOWN | Those screens were not reached |
| P0 | This server's JSON auth and lobby used by the original APK | NOT_SUPPORTED | `docs/NETWORK_PROTOCOL.md` identifies the JSON contract as this project's design |
| P1 | Original matchmaking, gameplay, and match results | UNKNOWN | No match was observed |
| P1 | This server's queue, `app/game` loop, and stored results used by the original APK | NOT_SUPPORTED | The loop is this project's simulation |
| P2 | Original patch-list format | UNKNOWN | Only the progress text was seen |
| P2 | An update exchange that would clear that gate | NOT_SUPPORTED | This server does not implement the original update exchange |
| P2 | Original admin protocol | UNKNOWN | No admin session was observed |
| P2 | Admin application in the sibling admin repository | DOCUMENTED as absent | That repository's `AGENTS.md` and `docs/ARCHITECTURE.md` describe a documentation placeholder |

## This server's own features

`docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` lists account, lobby, matchmaking, gameplay, and result functions with `implementation_status` and `test_status`. Those columns describe this repository. The `compatibility_status` column stays `unknown` until an authorized original source is compared. This research does not supply that source.

Wallet amounts in `app/services/cosmetics_service.py` are CONFIRMED as this project's catalog: a new player starts at 500 coin and 20 diamond, with skins `recruit` (free), `field_jacket` (200 coin), and `night_ops` (15 diamond). Original shop prices are UNKNOWN. The original APK is NOT_SUPPORTED as a buyer of this catalog.

## What would change the conclusion

A later note can move an original-behavior cell only with a permitted observation that names its source. Reaching the original lobby by bypassing authentication, encryption, certificate pinning, anti-cheat, or access controls is not that observation. Connecting `com.ros.client` and recording this server's JSON is evidence about the independent client, and it leaves the original APK at NOT_SUPPORTED.

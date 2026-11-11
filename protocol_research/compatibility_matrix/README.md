# Compatibility matrix

Date: 2026-11-11. This note points at the matrix. It does not rewrite `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md`.

## How to read the two results together

| Result | Status | Where it is recorded |
| --- | --- | --- |
| Original APK as a client of this JSON server | NOT_SUPPORTED | `docs/COMPATIBILITY.md` |
| Original rule numbers versus `app/game` | UNKNOWN | `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` uses `unknown` on every `compatibility_status` cell. Count recorded there: 0 compatible, 43 unknown |
| This server's own routes and the in-memory match | CONFIRMED as this project's design, with `implementation_status` and `test_status` in the matrix | The matrix. A passing test is not original-client proof |
| Patch-list format, opcodes, encryption, discovery hosts | UNKNOWN | `protocol_research/message_catalog/README.md` |
| Admin application | DOCUMENTED as not built | Sibling admin repository `AGENTS.md` |

P0 startup of the original client is CONFIRMED through the patch gate and still NOT_SUPPORTED as a session on this server. P1 matchmaking, gameplay, and results are CONFIRMED only inside `app/game` and `docs/GAME_RULES.md`. P2 updates and admin have no original specification in this repository.

## Cells this note refuses to fill

- Changing a matrix row from `unknown` to a compatible original value.
- Treating pistol damage 22, rifle damage 16, map size 200, speed 5, or zone radii 110, 70, 40, 20, and 8 as original data. Those numbers are this server's independent design.
- Marking `com.ros.client` profile checks as proof that the original APK can connect.

The conclusion stays: the original client is not a client of this server. Original balance values stay UNKNOWN until a permitted source is compared.

# Evidence

Date: 2026-11-11. Each source is named with a repository-relative path. Sibling paths are relative to the client repository or the admin repository, not to this server tree.

## Status labels used in the set

CONFIRMED, DOCUMENTED, INFERRED, UNKNOWN, NOT_SUPPORTED. Definitions: `docs/PROTOCOL_RESEARCH.md`.

## Sources read for this record

| Source | What it contributes | Status of that contribution |
| --- | --- | --- |
| `docs/reverse-engineering/CLIENT_ANALYSIS.md` | Package identity, NeoX activity, patch-gate text, and the statement that a public search copied no packet fields | CONFIRMED observations. The public page is a citation, not a protocol |
| `docs/reverse-engineering/RESEARCH_INDEX.md` | DIS-0011 and DIS-0012 | DOCUMENTED discoveries. DIS-0012: the sibling archive has not been shown to speak this JSON API |
| `docs/reverse-engineering/NETWORK_INTERFACE.md` | This server's JSON names | DOCUMENTED. Original interface left as a hypothesis there, recorded here as UNKNOWN and NOT_SUPPORTED |
| `docs/NETWORK_PROTOCOL.md`, `docs/API_CONTRACT.md`, `docs/ARCHITECTURE.md` | Version 1 JSON, HTTP, and process shape | DOCUMENTED and implemented |
| `docs/GAMEPLAY_SYSTEMS.md`, `docs/GAME_RUNTIME.md` | Independent match rules and tick authority | DOCUMENTED |
| `app/networking/protocol.py` | Version 1 message literals | CONFIRMED |
| `app/game/rules.py`, `app/game/items.py` | Independent map, speed, weapon, and zone numbers | CONFIRMED. Original values UNKNOWN |
| `app/services/cosmetics_service.py` | Starter 500 coin, 20 diamond, skins `recruit`, `field_jacket`, `night_ops` | CONFIRMED. Original shop UNKNOWN |
| `app/api/v1/admin_maps.py` | Username allow-list for map publishing | CONFIRMED. This is not an admin application |
| `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` | Original-behavior column remains `unknown` | DOCUMENTED |
| Sibling `research/INDEX.md` | Phase 01 scope and the statement that Ghidra, `libclient.so` disassembly, and `assets/protocol_data` were not done | DOCUMENTED |
| Sibling `research/CLIENT_ARCHITECTURE.md` | Manifest identity and the patch-gate run | CONFIRMED |
| Sibling `research/MULTIPLAYER_RESEARCH.md` | No original packet capture. Independent JSON is a separate design | CONFIRMED |
| Sibling `research/GAMEPLAY_SYSTEMS.md` | Original gameplay numbers not observed | UNKNOWN for original values |
| Sibling `research/ASSET_INVENTORY.md` | Package sizes and native library names | CONFIRMED inventory. Internal behavior UNKNOWN |
| Sibling `research/OPEN_QUESTIONS.md` | Patch list, OBB contents, and `protocol_data` still blocked | UNKNOWN |
| Sibling `research/reports/PHASE-01-REPORT.md` | Inventory counts and the recommended independent-client path | DOCUMENTED |
| Sibling `Client/Documentation/PROVENANCE.md` | Package hashes and version identity | DOCUMENTED. Hashes are not copied into this folder |
| Sibling admin `AGENTS.md` and `docs/ARCHITECTURE.md` | No admin application | DOCUMENTED |

## Work not done for this record

| Action | Result |
| --- | --- |
| Downloading an APK | Not done |
| Opening `assets/protocol_data` | Not done. Contents UNKNOWN |
| Running Ghidra or disassembling `libclient.so` | Not done |
| Extracting OBB or XAPK meshes, textures, or audio | Not done |
| Copying publisher assets into this repository | Not done |
| Writing a hostname from the client as an endpoint | Not done |
| Implementing a patch-list response | Not done. Original update exchange is NOT_SUPPORTED |
| Editing the task registry, starting Docker, or running pytest | Not done. This record is documentation |

## INFERRED items accepted from the sibling notes

- Gameplay UI of the original client is native and packed, because the classified layouts are account-SDK chrome and the launched activity is `com.netease.neox.Client`.
- Several native libraries match audio, video, crash, and account-SDK names. The match is the filename only.

No further inference is added. In particular, nothing here infers an opcode, a header, a patch-list field, or a discovery host.

## Next step

Leave the original client at the patch gate. Exercise two `com.ros.client` sessions against this server's existing login, durable lobby, and `app/game` loop, and record that run as this project's behavior.

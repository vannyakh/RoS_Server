# Client inventory

Date: 2026-11-11. Sources are the sibling client repository and `docs/reverse-engineering/CLIENT_ANALYSIS.md`. This server repository does not store a second copy of the APK, XAPK, or OBB files.

## Original package

| Fact | Status | Source |
| --- | --- | --- |
| Package `com.netease.chiji` | CONFIRMED | Sibling `Client/Documentation/PROVENANCE.md` and `research/CLIENT_ARCHITECTURE.md` |
| versionName `1.610637.617289`, versionCode `1227927` | CONFIRMED | Same |
| Engine NetEase NeoX. Launcher `com.netease.neox.Launcher`. Game activity `com.netease.neox.Client` with native library name `client` | CONFIRMED | Sibling `research/CLIENT_ARCHITECTURE.md` |
| `libclient.so` present for `arm64-v8a` and `armeabi-v7a` | CONFIRMED as a file. Internal functions UNKNOWN | Sibling `research/ASSET_INVENTORY.md` |
| Five DEX files and an Apktool tree | CONFIRMED | Sibling `research/reports/PHASE-01-REPORT.md` |
| On-screen stop at "Retrieving patch lists 0.00%" | CONFIRMED | Sibling `research/CLIENT_ARCHITECTURE.md` |
| Login and lobby screens | UNKNOWN | They were not shown |
| Hashes of the four large packages | DOCUMENTED in the sibling file `Client/Documentation/PROVENANCE.md` | Not repeated here |

The XAPK filename includes a store label. That label is a distribution name. It is not an authorized publisher checksum. Status of that reading: DOCUMENTED in the sibling provenance note.

## What stayed closed

| Item | Status |
| --- | --- |
| `libclient.so` disassembly | Not run. Behavior inside the library is UNKNOWN |
| `assets/protocol_data` | Directory name CONFIRMED in the sibling asset listing. Contents UNKNOWN. Files were not opened |
| XAPK and both OBB packages | Present and hashed in the sibling provenance note. Not extracted. Terrain contents UNKNOWN |
| `Ios/` in the sibling repository | CONFIRMED empty |
| Android rebuild artifacts | Not modified and not used as a protocol source |

## Independent application

| Fact | Status |
| --- | --- |
| `Android_API_Client`, package `com.ros.client` | CONFIRMED as a separate Kotlin application in sibling `research/CLIENT_ARCHITECTURE.md` |
| It does not load `libclient.so` | DOCUMENTED in that same note |
| It is the client intended for this server's JSON | DOCUMENTED in `docs/CUSTOM_SERVER_ARCHITECTURE.md` |

## Inference

Gameplay presentation for the original package is inside the native client and the unread packages. The Android XML that was classified is account-SDK chrome, and the activity on screen was `com.netease.neox.Client`. That reading is INFERRED in sibling `research/CLIENT_ARCHITECTURE.md`. It does not identify a message field.

Other native-library roles that come only from filenames are INFERRED. `libclient.so` is the library named by the game activity, which is CONFIRMED. What that library sends on the network is UNKNOWN.

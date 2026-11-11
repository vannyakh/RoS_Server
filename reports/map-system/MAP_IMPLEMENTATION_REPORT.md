# Map implementation report

The first usable map milestone is in place for the independent server and the `com.ros.client` Android app. A publisher can create a draft, register a file, publish a real manifest hash, and the Android app can list, download, verify, and reuse that package.

## Live Island Alpha

The development database was upgraded from `93510e8bf194` to `b7e2c91a4d10` after a backup. The server was restarted with `MAP_PUBLISHERS=map_admin`.

| Call | Result |
| --- | --- |
| `POST /api/v1/auth/register` `map_admin` | 201 |
| `POST /api/v1/auth/login` | 200 |
| `POST /api/v1/admin/maps` `island_alpha` | 201 |
| `POST .../versions` `1.0.0` | 201 |
| `POST .../assets` `minimap/preview.png` | 201, SHA-256 `19995436b6f0e5ce0403c9735f4955710253c583b2775f147c8192d8a223e9a8` |
| `POST .../publish` | 200 `published`, manifest `08aeb999868cf5a977a5b37fb07065076c4a04f70eba6dac7cbfca090caa1db8` |
| `GET /api/v1/maps` | 200, `total` 1, slug `island_alpha` |

The PNG is an 8 by 8 image generated for this test. It is 74 bytes. The version also stores one region, one building placement, four spawn points, and one point of interest. There is no terrain mesh.

On LDPlayer `emulator-5554`, with `adb reverse tcp:8000 tcp:8000` and the debug APK installed:

- The map detail showed Island Alpha, version 1.0.0, `local_xyz_y_up_meters`, size 256 by 256, and 74 bytes.
- After download the status was `Verified and cached`.
- Cache path `files/maps/f9cc1ce5-fe90-4d0f-b0fc-d51e513ac96c/1.0.0/` contains `minimap/preview.png` and `installed.json`.
- `installed.json` is the manifest hash above.
- Device SHA-256 of `preview.png` equals the manifest file hash.
- Leaving the screen and opening Details again showed `Cached 1.0.0` and the preview node `map_preview`.

The API base URL on the device was left at `http://127.0.0.1:8000`.

## Automated tests

`tests/integration/test_map_catalog.py` covers publish and catalog, a second publish rejected with 409, an asset upload on a published version rejected with 409, a duplicate version, an out-of-bounds spawn, path `../secret.png`, a tampered file, a missing file, a non-publisher 403, and pinning a match.

The full suite at the end of implementation was `94 passed, 1 skipped`. The skip is the existing PostgreSQL test when `POSTGRES_TEST_URL` is unset. No test was deleted or skipped to clear a map failure.

The disposable migration `tmp_map_migration.db` was upgraded and downgraded before the development database was touched. That temporary file was removed. The development database was only upgraded.

## Task record

These states are the map milestone record. They were not written into `.cursor/management/tasks.json`, because that registry is owned by the CTO agent and uses a different status set.

| Task | State | Evidence |
| --- | --- | --- |
| MAP-001 Audit | DONE | `reports/map-system/MAP_AUDIT.md` |
| MAP-002 Models | DONE | `app/models/map_content.py`, revision `b7e2c91a4d10` |
| MAP-003 Catalog API | DONE | Public routes and `test_publish_catalog_and_verified_manifest` |
| MAP-004 Storage | DONE | `app/infrastructure/map_storage.py` |
| MAP-005 Validation | DONE | Path, type, size, and bounds checks |
| MAP-006 Manifest | DONE | Live hash matches the device file |
| MAP-007 Publishing | DONE | Island Alpha `published`; repeat publish returns 409 |
| MAP-008 Android browser | DONE | Device showed Island Alpha |
| MAP-009 Downloads and cache | DONE | Verified download, matching hash, reopen `Cached 1.0.0` |
| MAP-010 Preview | DONE | `map_preview` rendered the cached PNG |
| MAP-011 Runtime interface | DONE | `MapRuntime` and `MinimapPreview` only |
| MAP-012 Engine evaluation | DONE | `docs/MAP_ENGINE_EVALUATION.md` in the client repo. No engine was integrated |
| MAP-013 Regression | DONE | `94 passed, 1 skipped` |

## Not done

- No Godot, Unity, Unreal, or LibGDX project was added.
- Download interruption, a deliberate bad hash on the device, offline catalog, and a second map version were not exercised on LDPlayer. The client code retries a file twice, deletes a hash mismatch, and refuses to write `installed.json` until every file matches. The server tests cover a bad hash and a missing file at publish time.
- There is no cache-size eviction screen.
- Published asset URLs are unauthenticated. They are not signed, expiring URLs.
- Concurrent publish was not run as a multi-process test.
- The larger Island Alpha content list (terrain mesh, five buildings, two roads, a bridge model) is still future content. The published package is the metadata plus the generated minimap.

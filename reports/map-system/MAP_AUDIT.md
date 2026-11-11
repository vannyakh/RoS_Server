# Map system audit

Audit of the server and the independent Android client before the map content routes were added. The decompiled reference tree was not modified.

## Confirmed before this work

- FastAPI routes lived under `app/api/v1/` for health, auth, players, lobby, items, inventory, and match records. There was no `/api/v1/maps` router and no admin map router.
- `map_definitions` already existed as a reference catalog: `code`, `name`, `description`, `width`, `height`, metadata, and `is_active`. It had no versions, assets, or publish state.
- Item catalog routes were the pattern for paged reference data. They do not store binary files.
- Authentication is a bearer JWT plus a session row. There is no admin role.
- Alembic head before the map revision was `93510e8bf194`. `app/infrastructure/database.py` runs `alembic upgrade` for the development database.
- `app/infrastructure/storage.py` defines the repository root used by local files. Map bytes were not using it yet.
- The independent client is `Android_API_Client`, package `com.ros.client`. It already had connection, login, registration, profile, lobby, and diagnostics. It had no map browser, downloader, or cache.
- `Android/` and `Client/Decompiled` are the original client archive. They are read-only and are not the API client.

## Missing at audit time

- Versioned map packages, manifests, and SHA-256 checks.
- Asset storage separate from SQL.
- A publisher permission for map writes.
- Android catalog, download, cache, and preview.
- A 3D runtime. The Compose client is a management UI.

## Decisions

- Reuse `map_definitions` as the map identity. `code` is the slug. Do not add a second identity table.
- Gate publishing with `MAP_PUBLISHERS`, because no admin role exists.
- Store bytes under `storage/game_assets` through `MapStorage`. SQL stores the key and the hash.
- Keep `local_xyz_y_up_meters` and `portable_gltf` as labels. Do not bind FastAPI to Godot, Unity, Unreal, or LibGDX.
- Preview the first package with a PNG. `MapRuntime` only returns that preview file.
- Pin a match to `map_version_id` and `manifest_hash`.

## Blockers recorded during the audit

- Publishing stays closed until `MAP_PUBLISHERS` names at least one account.
- A 3D match cannot load from the Compose client. That choice is documented in the client engine evaluation and is still open.
- The live development database needed an upgrade to `b7e2c91a4d10` before the running server could serve map routes. The upgrade was applied after a backup. The previous revision was not rewritten.

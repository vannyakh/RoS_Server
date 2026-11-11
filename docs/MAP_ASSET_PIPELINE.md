# Map asset pipeline

Packaging is the admin API in `app/services/maps/`. `scripts/map_pipeline/README.md` is the operator checklist. The service is the validator.

Use original or licensed files. The Island Alpha minimap used for the first live package was generated in the publish request. It is an 8 by 8 PNG, 74 bytes, and it is not artwork from another game.

## Stages

1. `POST /api/v1/admin/maps` creates the definition.
2. `POST /api/v1/admin/maps/{map_id}/versions` records bounds and placements. Positions outside the box are rejected before a row is kept.
3. `POST /api/v1/admin/maps/{map_id}/assets` checks the suffix, path, and size, computes SHA-256, and writes `maps/{map_id}/{version}/{relative_path}` with `write_new`.
4. `POST /api/v1/admin/maps/{map_id}/publish` reads those bytes back. Size and hash must match the row. The manifest hash is computed from the canonical body and stored.
5. The Android client downloads the manifest, fetches each `asset_id`, checks SHA-256, and writes `installed.json` only after every file matches.

## Rejected input

| Check | Result |
| --- | --- |
| Empty file or file over 32 MiB | 422 |
| Suffix outside the allow list, including `.py`, `.exe`, `.sh`, `.bat`, `.cmd`, `.js`, `.dll`, `.so`, `.apk`, `.jar`, `.ps1` | 422 `Asset file type is not allowed` |
| `..`, an absolute path, or a dot segment | 422 `Asset path is not allowed` |
| Storage key with `..` | 422 `Invalid storage key` |
| Existing storage file | 409 `Stored asset already exists` |
| Spawn, object, region, or point outside the version box | 422 |
| Scale of zero or a non-finite coordinate | 422 |
| Publish with no assets, a missing file, or a hash that does not match the disk | 422, and the version stays `draft` |
| Upload or publish on a published version | 409 |

The pipeline does not extract zip archives. Each file is uploaded by its relative path, so an archive cannot choose a path outside the version directory.

glTF and GLB are accepted as files. The server does not parse meshes, textures, or engine coordinates. A later runtime converts `local_xyz_y_up_meters` into its own axes.

## Manifest hash

`app/services/maps/manifest.py` hashes the body before `manifest_hash` is added. The hash is lowercase hex SHA-256. Placeholder hashes are not written. The publish step uses the bytes on disk, not the hash the client claimed at upload time, because the server computed that hash itself and then reads the file again.

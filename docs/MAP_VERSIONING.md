# Map versioning

A match that uses a map stores three values: `map_id`, `map_version_id`, and `manifest_hash`. The display name is not enough, because a later publish of the same map is a different package.

## Rules

- A draft version can gain assets until it is published.
- Publish reads the files, writes one `map_publications` row, and sets `status` to `published`.
- A published version rejects another publish and rejects new assets.
- The same `map_id` and `version` string cannot be inserted twice.
- Changing a published map means `POST /api/v1/admin/maps/{map_id}/versions` with a new `major.minor.patch`.
- `schema_version` other than 1 is rejected. Shipping schema 2 means a new validator and an explicit client rule. Old published rows stay on schema 1.
- Pinning requires `status=published` and a stored manifest hash. A draft cannot be pinned.
- Retiring a version is a status the table allows. The current API does not change a published row to `retired`, so a pinned match keeps the version it stored.

## Hash

The manifest body is `coordinate_system`, `engine_profile`, `files`, `map_id`, `schema_version`, `slug`, and `version`. `files` are sorted by path. The hash covers that object and is then added as `manifest_hash`.

`GET /api/v1/maps/{map_id}/manifest` rebuilds the hash. A mismatch returns 409, so a client does not download a package whose stored hash drifted from the files.

## Publication

`publish` sets the hash, status, `published_at`, and `publisher_account_id` in one service commit, after `verified_manifest` returns. A failed hash check raises before that commit. Two publishes of the same version: the first returns 200, the second returns 409 `Map version is already published`.

SQLite serializes writers. A dedicated multi-process publish race was not added. The status check and the unique publication row are the guards that exist today.

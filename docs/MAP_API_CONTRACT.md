# Map API contract

These routes are on `app.api.v1.maps` and `app.api.v1.admin_maps`. Errors use `{"detail": "<message>"}`.

Public routes do not read the bearer token. Admin routes require an active account whose username is in `MAP_PUBLISHERS`.

## Public catalog

`GET /api/v1/maps?limit=20&offset=0`

`limit` is 1 to 100. The page is `items`, `total`, `limit`, `offset`. Each item:

```json
{
  "id": "<uuid>",
  "slug": "island_alpha",
  "name": "Island Alpha",
  "description": "Original test map",
  "current_version": "1.0.0",
  "manifest_hash": "<64 hex chars>",
  "download_size_bytes": 74
}
```

`slug` is `map_definitions.code`. Draft definitions are omitted. `current_version` is the latest published version. `download_size_bytes` is the sum of that version's asset sizes.

`GET /api/v1/maps/{map_id}` adds `width`, `height`, `coordinate_system`, `origin`, and `size`. `coordinate_system` is `local_xyz_y_up_meters`. A definition with no published version returns 404 `Map not found`.

`GET /api/v1/maps/{map_id}/versions` returns published rows: `id`, `version`, `schema_version`, `engine_profile`, `status`, `manifest_hash`, `published_at`.

`GET /api/v1/maps/{map_id}/manifest?version=1.0.0`

`version` is optional. The default is the latest published version. A missing version returns 404 `Map version not found`. If the stored hash does not match the package the server rebuilds, the route returns 409 `Stored manifest hash does not match the package`.

```json
{
  "coordinate_system": "local_xyz_y_up_meters",
  "engine_profile": "portable_gltf",
  "files": [
    {
      "asset_id": "<uuid>",
      "path": "minimap/preview.png",
      "sha256": "<64 hex chars>",
      "size_bytes": 74,
      "type": "minimap"
    }
  ],
  "map_id": "<uuid>",
  "schema_version": 1,
  "slug": "island_alpha",
  "version": "1.0.0",
  "manifest_hash": "<64 hex chars>"
}
```

`manifest_hash` is SHA-256 of the canonical JSON of every field except `manifest_hash`. Canonical JSON uses sorted keys, `separators=(",", ":")`, and ASCII encoding. `files` are sorted by `path`.

`GET /api/v1/maps/{map_id}/assets/{asset_id}` returns the file bytes and `Content-Disposition` with the file name only. An asset on a draft, another map, or a missing id returns 404 `Asset not found`.

## Administration

`POST /api/v1/admin/maps`

```json
{"code": "island_alpha", "name": "Island Alpha", "description": "Original test map", "width": 256, "height": 256}
```

`code` must match `^[a-z0-9_]{1,64}$`. Uppercase is rejected. A duplicate code returns 409 `Map slug already exists`. `width` and `height` are 1–100000. The response is `MapDefinitionResponse`: `id`, `code`, `name`, `description`, `details`, `is_active`, `created_at`, `updated_at`, `width`, `height`.

`PATCH /api/v1/admin/maps/{map_id}` accepts any of `name`, `description`, `width`, `height`. After a version is published, changing `width` or `height` returns 409 `Published map dimensions are immutable`.

`POST /api/v1/admin/maps/{map_id}/versions`

```json
{
  "version": "1.0.0",
  "schema_version": 1,
  "engine_profile": "portable_gltf",
  "origin": [0, 0, 0],
  "size": [256, 100, 256],
  "regions": [{"code": "village", "name": "Village", "minimum": [0, 0, 0], "maximum": [80, 20, 80]}],
  "objects": [{
    "object_code": "building_warehouse_001",
    "definition_code": "building_warehouse",
    "category": "building",
    "position": [20, 0, 30],
    "rotation": [0, 0, 0],
    "scale": [1, 1, 1],
    "collision": true,
    "navigation_obstacle": true,
    "interactive": false
  }],
  "spawn_points": [{"spawn_code": "spawn_001", "position": [10, 0, 10], "rotation_y": 0, "spawn_group": "alpha", "enabled": true}],
  "points_of_interest": [{"poi_code": "bridge", "name": "Bridge", "description": "", "position": [50, 0, 50], "icon": "marker"}]
}
```

`version` must match `major.minor.patch`. `schema_version` must be 1. `origin` and `size` are three finite numbers, and every size component must be greater than zero. Region, object, spawn, and point positions must lie inside the box. A repeated version string returns 409 `Map version already exists`. A repeated child code returns 409 `Map data conflicts with an existing row`.

`POST /api/v1/admin/maps/{map_id}/assets` is multipart. Fields are `version_id`, `asset_type`, `relative_path`, and the file field `upload`.

Allowed `asset_type` values: `terrain`, `environment`, `building`, `road`, `landmark`, `prop`, `collision`, `navigation`, `minimap`, `preview`, `map_definition`, `audio`.

Allowed suffixes: `.json`, `.png`, `.webp`, `.glb`, `.gltf`, `.bin`, `.txt`, `.ogg`. The server rejects empty files, files over 32 MiB, absolute paths, `..`, blank segments, and a leading dot on any segment. The same path with the same SHA-256 returns the existing row. A different hash for that path returns 409 `Asset path already registered`. A published version returns 409 `Published map versions are immutable`.

`POST /api/v1/admin/maps/{map_id}/publish` with `{"version_id": "<uuid>"}` re-reads every stored file, checks size and SHA-256, requires at least one asset, then sets `status` to `published` and stores `manifest_hash`. A second publish returns 409 `Map version is already published`. A missing or altered file returns 422.

`POST /api/v1/admin/maps/{map_id}/pin` with `{"version_id": "<uuid>", "match_id": "<uuid>"}` returns 204. It sets `matches.map_id`, `matches.map_version_id`, and `matches.manifest_hash`. The version must already be published. A missing match returns 404 `Match not found`.

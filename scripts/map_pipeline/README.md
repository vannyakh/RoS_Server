# Map pipeline checklist

The validator is `app/services/maps/`. This directory does not copy files and does not extract archives.

1. Confirm the file is original or licensed. Leave `Client/Decompiled` unchanged.
2. Export models as glTF or GLB when a model is needed. Keep one coordinate convention: `local_xyz_y_up_meters`.
3. Create the definition with `POST /api/v1/admin/maps`.
4. Create a draft version with bounds, regions, objects, spawn points, and points of interest.
5. Upload each file with `POST /api/v1/admin/maps/{map_id}/assets`. The relative path must stay inside the package.
6. Publish. The server hashes the stored bytes and rejects the version if any file is missing or altered.
7. Read `GET /api/v1/maps/{map_id}/manifest` and confirm every `sha256` is 64 hex characters from that publish.

Allowed suffixes and the 32 MiB limit are in `docs/MAP_ASSET_PIPELINE.md`.

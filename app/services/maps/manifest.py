"""Canonical manifest bytes. The hash covers every field except manifest_hash."""

import json

from app.services.maps.validation import COORDINATE_SYSTEM, sha256_hex


def manifest_body(map_id: str, code: str, version: str, schema_version: int, engine_profile: str, files: list[dict]) -> dict:
    return {
        "coordinate_system": COORDINATE_SYSTEM,
        "engine_profile": engine_profile,
        "files": sorted(files, key=lambda item: item["path"]),
        "map_id": map_id,
        "schema_version": schema_version,
        "slug": code,
        "version": version,
    }


def canonical_bytes(body: dict) -> bytes:
    return json.dumps(body, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")


def with_hash(body: dict) -> dict:
    signed = dict(body)
    signed["manifest_hash"] = sha256_hex(canonical_bytes(body))
    return signed

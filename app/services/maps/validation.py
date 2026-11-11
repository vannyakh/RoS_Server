"""Path, hash, and bounds checks for map packages. These functions do not touch the database."""

import hashlib
import math
import re
from pathlib import Path

from app.core.exceptions import AppError

COORDINATE_SYSTEM = "local_xyz_y_up_meters"
SCHEMA_VERSION = 1
MAX_ASSET_BYTES = 32 * 1024 * 1024
CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
ALLOWED_SUFFIXES = {".json", ".png", ".webp", ".glb", ".gltf", ".bin", ".txt", ".ogg"}
BLOCKED_SUFFIXES = {".py", ".exe", ".sh", ".bat", ".cmd", ".js", ".dll", ".so", ".apk", ".jar", ".ps1"}
ASSET_TYPES = {
    "terrain",
    "environment",
    "building",
    "road",
    "landmark",
    "prop",
    "collision",
    "navigation",
    "minimap",
    "preview",
    "map_definition",
    "audio",
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_code(value: str, label: str) -> str:
    if not CODE_PATTERN.match(value):
        raise AppError(422, f"{label} must be 1-64 letters, numbers, or underscores")
    return value


def require_version(value: str) -> str:
    if not VERSION_PATTERN.match(value):
        raise AppError(422, "Version must use major.minor.patch")
    return value


def require_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
        raise AppError(422, "Asset path is not allowed")
    suffix = Path(normalized).suffix.lower()
    if suffix in BLOCKED_SUFFIXES or suffix not in ALLOWED_SUFFIXES:
        raise AppError(422, "Asset file type is not allowed")
    if any(part.startswith(".") for part in Path(normalized).parts):
        raise AppError(422, "Asset path is not allowed")
    return normalized


def require_asset_type(value: str) -> str:
    if value not in ASSET_TYPES:
        raise AppError(422, "Asset type is not allowed")
    return value


def require_bytes(data: bytes) -> bytes:
    if not data:
        raise AppError(422, "Asset file is empty")
    if len(data) > MAX_ASSET_BYTES:
        raise AppError(422, "Asset file exceeds the size limit")
    return data


def require_finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise AppError(422, f"{label} must be a finite number")
    return value


def require_inside(origin: tuple[float, float, float], size: tuple[float, float, float], point: tuple[float, float, float], label: str) -> None:
    for start, length, value, axis in zip(origin, size, point, ("x", "y", "z"), strict=True):
        require_finite(value, f"{label} {axis}")
        if value < start or value > start + length:
            raise AppError(422, f"{label} is outside the map bounds")


def require_scale(scale: tuple[float, float, float]) -> None:
    for value, axis in zip(scale, ("x", "y", "z"), strict=True):
        require_finite(value, f"scale {axis}")
        if value <= 0:
            raise AppError(422, "Scale must be greater than zero")

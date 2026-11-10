"""Reject datasets that do not match the supported import version."""

SCHEMA_VERSION = 1


def require_version(payload: dict, name: str) -> None:
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"{name} schema_version must be {SCHEMA_VERSION}")


def require_fields(record: dict, fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if record.get(field) in (None, "")]
    if missing:
        raise ValueError(f"{label} is missing {', '.join(missing)}")

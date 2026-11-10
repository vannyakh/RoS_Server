"""Atomic JSON IO for management registries.

Backups are timestamped copies. Checkpoints, changelog rows, and discoveries are append-only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGEMENT = ROOT / ".cursor" / "management"
SCHEMAS = MANAGEMENT / "schemas"
BACKUP_DIR = MANAGEMENT / "backups"

SENSITIVE_PARTS = (".env", ".db", "credentials")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sensitive(path: Path) -> bool:
    text = str(path).lower().replace("\\", "/")
    return any(part in text for part in SENSITIVE_PARTS)


def atomic_write(path: Path, payload: dict, *, backup_dir: Path | None = None) -> Path | None:
    """Write JSON via a temp file. Copy the previous file before replacing it."""
    if _sensitive(path):
        raise ValueError(f"refusing to write a sensitive path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if path.is_file():
        destination = backup_dir or BACKUP_DIR
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
        backup_path = destination / f"{path.name}.{stamp}.json"
        backup_path.write_bytes(path.read_bytes())
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return backup_path


def append_unique(document: dict, key: str, record: dict, id_field: str) -> dict:
    """Append a record. Refuse to replace an id that is already stored."""
    rows = document.setdefault(key, [])
    record_id = record[id_field]
    if any(row.get(id_field) == record_id for row in rows):
        raise ValueError(f"append-only: refusing to overwrite {record_id}")
    rows.append(record)
    return document


def management_path(name: str) -> Path:
    return MANAGEMENT / name

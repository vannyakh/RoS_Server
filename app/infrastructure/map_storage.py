"""Local map file storage. Keys are relative. Clients never receive a filesystem path."""

from pathlib import Path

from app.core.exceptions import AppError
from app.infrastructure.storage import ROOT

DEFAULT_ROOT = ROOT / "storage" / "game_assets"


class MapStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or DEFAULT_ROOT).resolve()

    def resolve(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise AppError(422, "Invalid storage key")
        full = (self.root / relative).resolve()
        if not full.is_relative_to(self.root):
            raise AppError(422, "Invalid storage key")
        return full

    def write_new(self, key: str, data: bytes) -> None:
        path = self.resolve(key)
        if path.exists():
            raise AppError(409, "Stored asset already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        path = self.resolve(key)
        if not path.is_file():
            raise AppError(422, "Asset file is missing")
        return path.read_bytes()

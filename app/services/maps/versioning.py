"""Draft version rules."""

from app.core.exceptions import AppError
from app.models.map_content import MapVersion


def require_draft(version: MapVersion) -> None:
    if version.status != "draft":
        raise AppError(409, "Published map versions are immutable")

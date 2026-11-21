"""Display images for the admin console and clients, looked up by (kind, key).

The file lives in local storage (GAME_ASSET_DIR, default storage/game_assets/icons), named by
its SHA-256, and is never committed. `source` records where the operator got it.
"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin

# "model" holds a binary glTF (.glb) 3D model; the others hold images. "rank" is keyed by tier name
# (app/services/rank_tiers.py), "background" by the lobby theme prop id.
ASSET_KINDS = ("rank", "prop", "item", "character", "currency", "badge", "other", "model", "background")


class GameAsset(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "game_assets"
    __table_args__ = (
        UniqueConstraint("kind", "key", name="uq_game_assets_kind_key"),
        CheckConstraint("kind IN ('rank', 'prop', 'item', 'character', 'currency', 'badge', 'other', 'model', 'background')", name="kind"),
        CheckConstraint("size_bytes > 0", name="size_bytes"),
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # Lookup key within the kind: a prop id, item code, rank tier, char_type, currency code.
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # Provenance: where the file came from (file path in an extract, a URL, "drawn in-house").
    source: Mapped[str] = mapped_column(String(240), nullable=False, default="", server_default="")
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)

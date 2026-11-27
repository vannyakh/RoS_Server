"""Operator overrides of how an original-client item is sold in the in-game store.

One row per item (today only lobby themes). No row means the game's own mall listing applies.
The gateway reads these through /api/v1/gateway/store/listings.
"""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin

LISTING_CURRENCIES = ("diamond", "coin")


class StoreListingOverride(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "store_listing_overrides"
    __table_args__ = (
        CheckConstraint("category IN ('lobby_theme')", name="category"),
        CheckConstraint("currency IN ('diamond', 'coin')", name="currency"),
        CheckConstraint("price >= 0 AND price <= 1000000", name="price"),
    )

    item_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)  # original prop id
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    on_sale: Mapped[bool] = mapped_column(Boolean, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)

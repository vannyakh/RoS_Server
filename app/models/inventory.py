"""Player-owned items and currency. Quantities and balances cannot go below zero."""

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON, UpdatedAtMixin


class PlayerInventory(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "player_inventories"
    __table_args__ = (UniqueConstraint("player_id", name="uq_player_inventories_player_id"),)

    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)

    player: Mapped["Player"] = relationship(back_populates="inventory", lazy="raise")
    items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="inventory",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )


class InventoryItem(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity"),
        UniqueConstraint("inventory_id", "item_definition_id", name="uq_inventory_items_player_item"),
    )

    inventory_id: Mapped[str] = mapped_column(
        ForeignKey("player_inventories.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_definition_id: Mapped[str] = mapped_column(
        ForeignKey("item_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(default=0, nullable=False)

    inventory: Mapped[PlayerInventory] = relationship(back_populates="items", lazy="raise")
    item_definition: Mapped["ItemDefinition"] = relationship(lazy="raise")


class PlayerCurrency(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "player_currencies"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance"),
        UniqueConstraint("player_id", "currency_code", name="uq_player_currencies_code"),
    )

    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(16), nullable=False)
    balance: Mapped[int] = mapped_column(default=0, nullable=False)

    player: Mapped["Player"] = relationship(back_populates="currencies", lazy="raise")


class CurrencyTransaction(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "currency_transactions"

    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)
    balance_after: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict | None] = mapped_column("metadata", PortableJSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

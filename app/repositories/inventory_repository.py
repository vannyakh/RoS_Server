"""Inventory and currency queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import InventoryItem, PlayerCurrency, PlayerInventory
from app.models.player import Player


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def inventory_for_player(self, player_id: str) -> PlayerInventory | None:
        return await self.session.scalar(
            select(PlayerInventory)
            .where(PlayerInventory.player_id == player_id)
            .options(selectinload(PlayerInventory.items))
        )

    async def item(self, inventory_id: str, item_definition_id: str) -> InventoryItem | None:
        return await self.session.scalar(
            select(InventoryItem).where(
                InventoryItem.inventory_id == inventory_id,
                InventoryItem.item_definition_id == item_definition_id,
            )
        )

    async def currency(self, player_id: str, currency_code: str) -> PlayerCurrency | None:
        return await self.session.scalar(
            select(PlayerCurrency).where(
                PlayerCurrency.player_id == player_id,
                PlayerCurrency.currency_code == currency_code,
            )
        )

    async def currencies(self, player_id: str) -> list[PlayerCurrency]:
        rows = await self.session.scalars(
            select(PlayerCurrency).where(PlayerCurrency.player_id == player_id).order_by(PlayerCurrency.currency_code)
        )
        return list(rows.all())

    async def player_by_account(self, account_id: str) -> Player | None:
        return await self.session.scalar(select(Player).where(Player.account_id == account_id))

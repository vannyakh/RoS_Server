"""Inventory changes run in one transaction and refuse a negative quantity."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.inventory import CurrencyTransaction, InventoryItem, PlayerCurrency, PlayerInventory
from app.repositories.game_data_repository import GameDataRepository
from app.repositories.inventory_repository import InventoryRepository


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = InventoryRepository(session)
        self.items = GameDataRepository(session)

    async def view(self, player_id: str) -> dict:
        holder = await self.inventory.inventory_for_player(player_id)
        currencies = await self.inventory.currencies(player_id)
        return {
            "id": holder.id if holder else None,
            "player_id": player_id,
            "items": list(holder.items) if holder else [],
            "currencies": currencies,
        }

    async def add_item(self, player_id: str, item_code: str, quantity: int, *, commit: bool = True) -> InventoryItem:
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise AppError(422, "Quantity must be a positive integer")
        definition = await self.items.item_by_code(item_code)
        if definition is None:
            raise AppError(404, "Item definition not found")
        holder = await self._holder(player_id)
        row = await self.inventory.item(holder.id, definition.id)
        if row is None:
            row = InventoryItem(inventory_id=holder.id, item_definition_id=definition.id, quantity=0)
            self.session.add(row)
        if row.quantity + quantity > definition.max_stack:
            raise AppError(409, "Stack limit exceeded")
        row.quantity += quantity
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        else:
            await self.session.flush()
        return row

    async def remove_item(self, player_id: str, item_code: str, quantity: int) -> InventoryItem:
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise AppError(422, "Quantity must be a positive integer")
        definition = await self.items.item_by_code(item_code)
        if definition is None:
            raise AppError(404, "Item definition not found")
        holder = await self._holder(player_id)
        row = await self.inventory.item(holder.id, definition.id)
        if row is None or row.quantity < quantity:
            raise AppError(409, "Not enough items")
        row.quantity -= quantity
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def apply_currency(
        self,
        player_id: str,
        currency_code: str,
        amount: int,
        reason: str,
        *,
        commit: bool = True,
    ) -> PlayerCurrency:
        if not isinstance(amount, int) or isinstance(amount, bool) or amount == 0:
            raise AppError(422, "Currency amount must be a non-zero integer")
        row = await self.inventory.currency(player_id, currency_code)
        if row is None:
            row = PlayerCurrency(player_id=player_id, currency_code=currency_code, balance=0)
            self.session.add(row)
            await self.session.flush()
        balance = row.balance + amount
        if balance < 0:
            raise AppError(409, "Insufficient balance")
        row.balance = balance
        self.session.add(
            CurrencyTransaction(
                player_id=player_id,
                currency_code=currency_code,
                amount=amount,
                balance_after=balance,
                reason=reason,
            )
        )
        if commit:
            await self.session.commit()
            await self.session.refresh(row)
        else:
            await self.session.flush()
        return row

    async def _holder(self, player_id: str) -> PlayerInventory:
        holder = await self.inventory.inventory_for_player(player_id)
        if holder is None:
            holder = PlayerInventory(player_id=player_id)
            self.session.add(holder)
            await self.session.flush()
        return holder

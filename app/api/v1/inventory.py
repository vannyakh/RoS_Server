"""Durable inventory for the authenticated player. Match loot stays in memory."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player
from app.infrastructure.database import get_db
from app.models.player import Player
from app.schemas.inventory import CurrencyChange, CurrencyResponse, InventoryItemResponse, InventoryResponse, ItemQuantityChange
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=InventoryResponse)
async def inventory(
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await InventoryService(db).view(player.id)


@router.post("/items", response_model=InventoryItemResponse)
async def add_item(
    body: ItemQuantityChange,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    row = await InventoryService(db).add_item(player.id, body.item_code, body.quantity)
    return InventoryItemResponse.model_validate(row, from_attributes=True)


@router.post("/items/remove", response_model=InventoryItemResponse)
async def remove_item(
    body: ItemQuantityChange,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemResponse:
    row = await InventoryService(db).remove_item(player.id, body.item_code, body.quantity)
    return InventoryItemResponse.model_validate(row, from_attributes=True)


@router.post("/currency", response_model=CurrencyResponse)
async def change_currency(
    body: CurrencyChange,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CurrencyResponse:
    row = await InventoryService(db).apply_currency(player.id, body.currency_code, body.amount, body.reason)
    return CurrencyResponse.model_validate(row, from_attributes=True)

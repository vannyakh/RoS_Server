"""Independent coin, diamond, and skin catalog. These prices are not original game values."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.game_data import ItemDefinition
from app.models.inventory import InventoryItem, PlayerInventory
from app.models.player import Player
from app.services.inventory_service import InventoryService

COIN = "coin"
DIAMOND = "diamond"
WALLET_CODES = (COIN, DIAMOND)
STARTER_BALANCES = {COIN: 500, DIAMOND: 20}


@dataclass(frozen=True)
class SkinOffer:
    code: str
    name: str
    currency: str | None
    price: int


SKINS = (
    SkinOffer("recruit", "Recruit", None, 0),
    SkinOffer("field_jacket", "Field Jacket", COIN, 200),
    SkinOffer("night_ops", "Night Ops", DIAMOND, 15),
)
SKIN_BY_CODE = {skin.code: skin for skin in SKINS}


def _skin(code: str) -> SkinOffer:
    skin = SKIN_BY_CODE.get(code)
    if skin is None:
        raise AppError(404, "Skin not found")
    return skin


async def ensure_starter(session: AsyncSession, player: Player, *, commit: bool) -> None:
    await _ensure_definitions(session)
    inventory = InventoryService(session)
    created = False
    for code, amount in STARTER_BALANCES.items():
        if await inventory.inventory.currency(player.id, code) is None:
            await inventory.apply_currency(player.id, code, amount, "starter", commit=False)
            created = True
    if not await _owns(session, player.id, "recruit"):
        await inventory.add_item(player.id, "recruit", 1, commit=False)
        created = True
    if player.avatar_id is None:
        player.avatar_id = "recruit"
        created = True
    if commit and created:
        await session.commit()
        await session.refresh(player)


async def wallet_snapshot(session: AsyncSession, player: Player) -> dict:
    await ensure_starter(session, player, commit=True)
    inventory = InventoryService(session)
    balances = {row.currency_code: row.balance for row in await inventory.inventory.currencies(player.id)}
    owned = await _owned_codes(session, player.id)
    return {
        "coin": balances.get(COIN, 0),
        "diamond": balances.get(DIAMOND, 0),
        "equipped_skin": player.avatar_id,
        "owned_skins": owned,
    }


async def skin_catalog(session: AsyncSession, player: Player) -> list[dict]:
    snapshot = await wallet_snapshot(session, player)
    owned = set(snapshot["owned_skins"])
    equipped = snapshot["equipped_skin"]
    return [
        {
            "code": skin.code,
            "name": skin.name,
            "currency": skin.currency,
            "price": skin.price,
            "owned": skin.code in owned,
            "equipped": skin.code == equipped,
        }
        for skin in SKINS
    ]


async def purchase_skin(session: AsyncSession, player: Player, code: str) -> dict:
    skin = _skin(code)
    await ensure_starter(session, player, commit=True)
    if await _owns(session, player.id, skin.code):
        raise AppError(409, "Skin already owned")
    inventory = InventoryService(session)
    if skin.price > 0 and skin.currency is not None:
        await inventory.apply_currency(player.id, skin.currency, -skin.price, "skin_purchase", commit=False)
    await inventory.add_item(player.id, skin.code, 1, commit=False)
    await session.commit()
    return await wallet_snapshot(session, player)


async def equip_skin(session: AsyncSession, player: Player, code: str) -> dict:
    _skin(code)
    await ensure_starter(session, player, commit=True)
    if not await _owns(session, player.id, code):
        raise AppError(409, "Skin not owned")
    player.avatar_id = code
    await session.commit()
    await session.refresh(player)
    return await wallet_snapshot(session, player)


async def _ensure_definitions(session: AsyncSession) -> None:
    for skin in SKINS:
        found = await session.scalar(select(ItemDefinition.id).where(ItemDefinition.code == skin.code))
        if found is None:
            session.add(
                ItemDefinition(
                    code=skin.code,
                    name=skin.name,
                    description="Independent cosmetic for this server.",
                    category="skin",
                    max_stack=1,
                )
            )
    await session.flush()


async def _owns(session: AsyncSession, player_id: str, code: str) -> bool:
    quantity = await session.scalar(
        select(InventoryItem.quantity)
        .join(ItemDefinition, ItemDefinition.id == InventoryItem.item_definition_id)
        .join(PlayerInventory, PlayerInventory.id == InventoryItem.inventory_id)
        .where(
            PlayerInventory.player_id == player_id,
            ItemDefinition.code == code,
        )
    )
    return quantity is not None and quantity > 0


async def _owned_codes(session: AsyncSession, player_id: str) -> list[str]:
    rows = await session.scalars(
        select(ItemDefinition.code)
        .join(InventoryItem, InventoryItem.item_definition_id == ItemDefinition.id)
        .join(PlayerInventory, PlayerInventory.id == InventoryItem.inventory_id)
        .where(
            PlayerInventory.player_id == player_id,
            ItemDefinition.category == "skin",
            InventoryItem.quantity > 0,
        )
        .order_by(ItemDefinition.code)
    )
    return list(rows.all())

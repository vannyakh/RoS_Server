"""Development item, weapon, equipment, and vehicle fixtures."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.seeds._upsert import upsert_code
from app.models.game_data import EquipmentDefinition, ItemDefinition, VehicleDefinition, WeaponDefinition


async def seed_items(session: AsyncSession) -> None:
    item = await upsert_code(
        session,
        ItemDefinition,
        "TEST_ITEM",
        name="Test Item",
        description="Development stackable item.",
        category="misc",
        max_stack=20,
        details={"fixture": True},
    )
    weapon_item = await upsert_code(
        session,
        ItemDefinition,
        "TEST_WEAPON_ITEM",
        name="Test Weapon Item",
        description="Development weapon item.",
        category="weapon",
        max_stack=1,
        details={"fixture": True},
    )
    await upsert_code(
        session,
        WeaponDefinition,
        "TEST_WEAPON",
        name="Test Weapon",
        description="Independent development weapon. Not an official asset.",
        item_definition_id=weapon_item.id,
        damage=1,
        range_units=1,
        magazine_size=1,
        details={"fixture": True},
    )
    await upsert_code(
        session,
        EquipmentDefinition,
        "TEST_EQUIPMENT",
        name="Test Equipment",
        description="Development equipment slot.",
        slot="misc",
        details={"fixture": True},
    )
    await upsert_code(
        session,
        VehicleDefinition,
        "TEST_VEHICLE",
        name="Test Vehicle",
        description="Development vehicle.",
        seats=1,
        details={"fixture": True},
    )
    await session.flush()
    stored = await session.scalar(select(ItemDefinition).where(ItemDefinition.code == "TEST_ITEM"))
    if stored is None or stored.id != item.id:
        raise RuntimeError("Item seed did not persist")

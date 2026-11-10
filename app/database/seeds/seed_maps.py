"""Development map fixture."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.seeds._upsert import upsert_code
from app.models.game_data import MapDefinition


async def seed_maps(session: AsyncSession) -> None:
    await upsert_code(
        session,
        MapDefinition,
        "TEST_MAP",
        name="Test Map",
        description="Empty development map.",
        width=200,
        height=200,
        details={"fixture": True},
    )

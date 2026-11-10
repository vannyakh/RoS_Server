"""Development achievement fixture."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.seeds._upsert import upsert_code
from app.models.game_data import AchievementDefinition


async def seed_achievements(session: AsyncSession) -> None:
    await upsert_code(
        session,
        AchievementDefinition,
        "TEST_ACHIEVEMENT",
        name="Test Achievement",
        description="Awarded only by this development server.",
        points=1,
        details={"fixture": True},
    )

"""Development rank fixture."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.seeds._upsert import upsert_code
from app.models.game_data import RankDefinition


async def seed_ranks(session: AsyncSession) -> None:
    await upsert_code(
        session,
        RankDefinition,
        "TEST_RANK",
        name="Test Rank",
        description="Starting development rank.",
        threshold_score=0,
        details={"fixture": True},
    )

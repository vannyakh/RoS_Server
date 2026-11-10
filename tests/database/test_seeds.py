"""Reference seeds can run more than once."""

from sqlalchemy import func, select

from app.database.seeds.seed_all import seed_all
from app.models.game_data import GameMode, ItemDefinition


async def test_seeds_are_idempotent(db_session):
    await seed_all(db_session)
    await seed_all(db_session)
    await db_session.commit()
    modes = await db_session.scalar(select(func.count()).select_from(GameMode))
    items = await db_session.scalar(select(func.count()).select_from(ItemDefinition))
    assert modes == 3
    assert items == 2

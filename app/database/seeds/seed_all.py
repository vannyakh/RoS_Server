"""Apply every development fixture in one transaction."""

import asyncio

from app.database.seeds.seed_achievements import seed_achievements
from app.database.seeds.seed_game_modes import seed_game_modes
from app.database.seeds.seed_items import seed_items
from app.database.seeds.seed_maps import seed_maps
from app.database.seeds.seed_ranks import seed_ranks
from app.infrastructure.database import SessionLocal, init_db, close_db


async def seed_all(session=None) -> None:
    if session is None:
        await init_db()
        async with SessionLocal() as owned:
            await _run(owned)
            await owned.commit()
        await close_db()
        return
    await _run(session)


async def _run(session) -> None:
    await seed_game_modes(session)
    await seed_maps(session)
    await seed_items(session)
    await seed_ranks(session)
    await seed_achievements(session)


if __name__ == "__main__":
    asyncio.run(seed_all())

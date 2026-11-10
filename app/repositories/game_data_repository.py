"""Reference-data queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_data import ItemDefinition


class GameDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def item_by_code(self, code: str) -> ItemDefinition | None:
        return await self.session.scalar(select(ItemDefinition).where(ItemDefinition.code == code))

    async def items(self, limit: int, offset: int) -> tuple[list[ItemDefinition], int]:
        rows = (
            await self.session.scalars(
                select(ItemDefinition).order_by(ItemDefinition.code).limit(limit).offset(offset)
            )
        ).all()
        total = int(await self.session.scalar(select(func.count()).select_from(ItemDefinition)) or 0)
        return list(rows), total

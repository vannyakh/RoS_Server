"""Reference-data reads."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.game_data_repository import GameDataRepository
from app.schemas.common import Page
from app.schemas.game_data import ItemDefinitionResponse


class GameDataService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = GameDataRepository(session)

    async def list_items(self, limit: int, offset: int) -> Page[ItemDefinitionResponse]:
        rows, total = await self.repository.items(limit, offset)
        return Page(
            items=[ItemDefinitionResponse.model_validate(row, from_attributes=True) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

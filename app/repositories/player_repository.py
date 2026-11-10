"""Player profile queries. Collections are loaded only when a caller asks for them."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.player import Player, PlayerStatistics


class PlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_account_id(self, account_id: str) -> Player | None:
        return await self.session.scalar(select(Player).where(Player.account_id == account_id))

    async def by_nickname(self, nickname: str) -> Player | None:
        return await self.session.scalar(select(Player).where(Player.nickname == nickname))

    async def statistics_for_account(self, account_id: str) -> PlayerStatistics | None:
        return await self.session.scalar(
            select(PlayerStatistics)
            .join(Player, Player.id == PlayerStatistics.player_id)
            .where(Player.account_id == account_id)
        )

    async def statistics_for_player(self, player_id: str) -> PlayerStatistics | None:
        return await self.session.scalar(
            select(PlayerStatistics).where(PlayerStatistics.player_id == player_id)
        )

    async def with_statistics(self, player_id: str) -> Player | None:
        return await self.session.scalar(
            select(Player).where(Player.id == player_id).options(selectinload(Player.statistics))
        )

    async def add(self, player: Player) -> Player:
        self.session.add(player)
        await self.session.flush()
        return player

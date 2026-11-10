"""Lobby membership queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lobby import Lobby, LobbyMember, Team, TeamMember


class LobbyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_id(self, lobby_id: str) -> Lobby | None:
        return await self.session.get(Lobby, lobby_id)

    async def member(self, lobby_id: str, player_id: str) -> LobbyMember | None:
        return await self.session.scalar(
            select(LobbyMember).where(LobbyMember.lobby_id == lobby_id, LobbyMember.player_id == player_id)
        )

    async def member_count(self, lobby_id: str) -> int:
        value = await self.session.scalar(
            select(func.count()).select_from(LobbyMember).where(LobbyMember.lobby_id == lobby_id)
        )
        return int(value or 0)

    async def team(self, team_id: str) -> Team | None:
        return await self.session.get(Team, team_id)

    async def team_member(self, lobby_id: str, player_id: str) -> TeamMember | None:
        return await self.session.scalar(
            select(TeamMember).where(TeamMember.lobby_id == lobby_id, TeamMember.player_id == player_id)
        )

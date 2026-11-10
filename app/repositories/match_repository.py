"""Match record queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchParticipant


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_id(self, match_id: str) -> Match | None:
        return await self.session.get(Match, match_id)

    async def by_code(self, match_code: str) -> Match | None:
        return await self.session.scalar(select(Match).where(Match.match_code == match_code))

    async def participant(self, match_id: str, player_id: str) -> MatchParticipant | None:
        return await self.session.scalar(
            select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.player_id == player_id,
            )
        )

    async def recent(self, limit: int, offset: int) -> list[Match]:
        rows = await self.session.scalars(
            select(Match).order_by(Match.created_at.desc()).limit(limit).offset(offset)
        )
        return list(rows.all())

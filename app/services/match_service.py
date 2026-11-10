"""Stored match records and result finalization. This is not the live simulation."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.match import Match, MatchParticipant, MatchResult, MatchStatistics
from app.models.types import utc_now
from app.repositories.match_repository import MatchRepository

_TRANSITIONS = {
    "scheduled": {"lobby", "cancelled"},
    "lobby": {"running", "cancelled"},
    "running": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class MatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.matches = MatchRepository(session)

    async def create(self, match_code: str, max_players: int, game_mode_id: str | None = None) -> Match:
        match = Match(match_code=match_code, max_players=max_players, game_mode_id=game_mode_id, status="scheduled")
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def transition(self, match_id: str, status: str) -> Match:
        match = await self._match(match_id)
        if status not in _TRANSITIONS[match.status]:
            raise AppError(409, "Invalid match transition")
        now = utc_now()
        match.status = status
        if status == "running":
            match.started_at = now
        if status in {"completed", "cancelled"}:
            match.ended_at = now
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def add_participant(self, match_id: str, player_id: str) -> MatchParticipant:
        match = await self._match(match_id)
        if match.status not in {"scheduled", "lobby"}:
            raise AppError(409, "Match is not accepting players")
        if await self.matches.participant(match_id, player_id) is not None:
            raise AppError(409, "Player is already in the match")
        if match.current_players >= match.max_players:
            raise AppError(409, "Match is full")
        participant = MatchParticipant(match_id=match_id, player_id=player_id, joined_at=datetime.now(timezone.utc))
        match.current_players += 1
        self.session.add(participant)
        await self.session.commit()
        await self.session.refresh(participant)
        return participant

    async def finalize(self, match_id: str, results: list[dict]) -> Match:
        match = await self._match(match_id)
        if match.status != "running":
            raise AppError(409, "Only a running match can be finalized")
        total_kills = 0
        seen: set[str] = set()
        for result in results:
            player_id = result["player_id"]
            if player_id in seen:
                raise AppError(409, "Duplicate match result")
            seen.add(player_id)
            if await self.matches.participant(match_id, player_id) is None:
                raise AppError(409, "Result player is not a participant")
            kills = int(result.get("kills") or 0)
            total_kills += kills
            self.session.add(
                MatchResult(
                    match_id=match_id,
                    player_id=player_id,
                    placement=int(result["placement"]),
                    kills=kills,
                    score=int(result.get("score") or 0),
                    rewards=dict(result.get("rewards") or {}),
                )
            )
        match.status = "completed"
        match.ended_at = utc_now()
        duration_seconds = 0
        if match.started_at is not None and match.ended_at is not None:
            started = match.started_at if match.started_at.tzinfo else match.started_at.replace(tzinfo=timezone.utc)
            ended = match.ended_at if match.ended_at.tzinfo else match.ended_at.replace(tzinfo=timezone.utc)
            duration_seconds = max(0, int((ended - started).total_seconds()))
        self.session.add(
            MatchStatistics(
                match_id=match_id,
                participant_count=len(results),
                total_kills=total_kills,
                duration_seconds=duration_seconds,
                summary={"source": "finalize"},
            )
        )
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def _match(self, match_id: str) -> Match:
        match = await self.matches.by_id(match_id)
        if match is None:
            raise AppError(404, "Match not found")
        return match

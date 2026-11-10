"""Durable lobby membership. The live queue remains in memory and is not written every tick."""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.game.engine import game_engine
from app.models.lobby import Lobby, LobbyMember, Team, TeamMember
from app.repositories.lobby_repository import LobbyRepository


async def lobby_status() -> dict:
    return await game_engine.lobby_status()


class LobbyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lobbies = LobbyRepository(session)

    async def open_lobby(self, code: str, max_players: int, game_mode_id: str | None = None) -> Lobby:
        if max_players < 1:
            raise AppError(422, "Lobby capacity must be at least 1")
        lobby = Lobby(code=code, max_players=max_players, game_mode_id=game_mode_id, status="open")
        self.session.add(lobby)
        await self._commit()
        await self.session.refresh(lobby)
        return lobby

    async def join(self, lobby_id: str, player_id: str) -> LobbyMember:
        lobby = await self.lobbies.by_id(lobby_id)
        if lobby is None or lobby.status != "open":
            raise AppError(409, "Lobby is not open")
        if await self.lobbies.member(lobby_id, player_id) is not None:
            raise AppError(409, "Player is already in the lobby")
        count = await self.lobbies.member_count(lobby_id)
        if count >= lobby.max_players:
            raise AppError(409, "Lobby is full")
        member = LobbyMember(lobby_id=lobby_id, player_id=player_id, joined_at=datetime.now(timezone.utc))
        lobby.current_players = count + 1
        self.session.add(member)
        await self._commit("Player is already in the lobby")
        await self.session.refresh(member)
        return member

    async def create_team(self, lobby_id: str, code: str, name: str, player_id: str) -> Team:
        lobby = await self.lobbies.by_id(lobby_id)
        if lobby is None or lobby.status != "open":
            raise AppError(409, "Lobby is not open")
        if await self.lobbies.member(lobby_id, player_id) is None:
            raise AppError(409, "Player must join the lobby first")
        team = Team(lobby_id=lobby_id, code=code, name=name)
        self.session.add(team)
        await self._commit("Team code already exists")
        await self.session.refresh(team)
        return team

    async def join_team(self, team_id: str, player_id: str) -> TeamMember:
        team = await self.lobbies.team(team_id)
        if team is None:
            raise AppError(404, "Team not found")
        if await self.lobbies.member(team.lobby_id, player_id) is None:
            raise AppError(409, "Player must join the lobby first")
        if await self.lobbies.team_member(team.lobby_id, player_id) is not None:
            raise AppError(409, "Player is already on a team in this lobby")
        member = TeamMember(
            team_id=team.id,
            lobby_id=team.lobby_id,
            player_id=player_id,
            joined_at=datetime.now(timezone.utc),
        )
        self.session.add(member)
        await self._commit("Player is already on a team in this lobby")
        await self.session.refresh(member)
        return member

    async def _commit(self, conflict: str = "Lobby code already exists") -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, conflict) from exc

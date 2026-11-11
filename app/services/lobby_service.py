"""Durable lobby membership. The live queue remains in memory and is not written every tick."""

from datetime import datetime, timezone

from sqlalchemy import delete, update
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

    async def details(self, lobby_id: str, player_id: str) -> Lobby:
        lobby = await self._open_or_found(lobby_id, require_open=False)
        if await self.lobbies.member(lobby_id, player_id) is None:
            raise AppError(403, "Player is not in the lobby")
        return lobby

    async def list_members(self, lobby_id: str, player_id: str) -> list[LobbyMember]:
        await self.details(lobby_id, player_id)
        return await self.lobbies.members(lobby_id)

    async def join(self, lobby_id: str, player_id: str) -> LobbyMember:
        lobby = await self._open_or_found(lobby_id, require_open=True)
        if await self.lobbies.member(lobby_id, player_id) is not None:
            raise AppError(409, "Player is already in the lobby")
        reserved = await self.session.execute(
            update(Lobby)
            .where(Lobby.id == lobby_id, Lobby.status == "open", Lobby.current_players < Lobby.max_players)
            .values(current_players=Lobby.current_players + 1)
            .execution_options(synchronize_session=False)
        )
        if reserved.rowcount != 1:
            await self.session.rollback()
            current = await self.lobbies.by_id(lobby_id)
            if current is None:
                raise AppError(404, "Lobby not found")
            if current.status != "open":
                raise AppError(409, "Lobby is not open")
            raise AppError(409, "Lobby is full")
        self.session.expire(lobby, ["current_players"])
        member = LobbyMember(lobby_id=lobby_id, player_id=player_id, joined_at=datetime.now(timezone.utc))
        self.session.add(member)
        await self._commit("Player is already in the lobby")
        await self.session.refresh(member)
        return member

    async def create_team(self, lobby_id: str, code: str, name: str, player_id: str) -> Team:
        await self._open_or_found(lobby_id, require_open=True)
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

    async def leave_team(self, team_id: str, player_id: str) -> None:
        team = await self.lobbies.team(team_id)
        if team is None:
            raise AppError(404, "Team not found")
        member = await self.lobbies.team_member(team.lobby_id, player_id)
        if member is None or member.team_id != team_id:
            raise AppError(404, "Player is not on the team")
        await self.session.delete(member)
        await self._commit()

    async def leave(self, lobby_id: str, player_id: str) -> None:
        lobby = await self.lobbies.by_id(lobby_id)
        member = await self.lobbies.member(lobby_id, player_id)
        if lobby is None or member is None:
            raise AppError(404, "Player is not in the lobby")
        await self.session.execute(
            delete(TeamMember).where(TeamMember.lobby_id == lobby_id, TeamMember.player_id == player_id)
        )
        await self.session.delete(member)
        await self.session.flush()
        lobby.current_players = await self.lobbies.member_count(lobby_id)
        if lobby.current_players == 0 and lobby.status == "open":
            lobby.status = "closed"
            lobby.closed_at = datetime.now(timezone.utc)
        await self._commit()

    async def set_ready(self, lobby_id: str, player_id: str, ready: bool) -> LobbyMember:
        await self._open_or_found(lobby_id, require_open=True)
        member = await self.lobbies.member(lobby_id, player_id)
        if member is None:
            raise AppError(409, "Player must join the lobby first")
        member.ready = ready
        await self._commit()
        await self.session.refresh(member)
        return member

    async def _open_or_found(self, lobby_id: str, *, require_open: bool) -> Lobby:
        lobby = await self.lobbies.by_id(lobby_id)
        if lobby is None:
            raise AppError(404, "Lobby not found")
        if require_open and lobby.status != "open":
            raise AppError(409, "Lobby is not open")
        return lobby

    async def _commit(self, conflict: str = "Lobby code already exists") -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, conflict) from exc

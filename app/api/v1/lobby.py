"""Live queue status and durable lobby membership."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player
from app.infrastructure.database import get_db
from app.models.player import Player
from app.schemas.lobby import (
    LobbyCreate,
    LobbyMemberResponse,
    ReadyUpdate,
    LobbyResponse,
    TeamCreate,
    TeamMemberResponse,
    TeamResponse,
)
from app.services.lobby_service import LobbyService, lobby_status

router = APIRouter(prefix="/lobby", tags=["Lobby"])


@router.get("")
async def lobby() -> dict:
    return await lobby_status()


@router.post("", response_model=LobbyResponse, status_code=201)
async def open_lobby(
    body: LobbyCreate,
    _player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> LobbyResponse:
    created = await LobbyService(db).open_lobby(body.code, body.max_players, body.game_mode_id)
    return LobbyResponse.model_validate(created, from_attributes=True)


@router.post("/{lobby_id}/members", response_model=LobbyMemberResponse, status_code=201)
async def join_lobby(
    lobby_id: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> LobbyMemberResponse:
    member = await LobbyService(db).join(lobby_id, player.id)
    return LobbyMemberResponse.model_validate(member, from_attributes=True)


@router.delete("/{lobby_id}/members", status_code=204)
async def leave_lobby(
    lobby_id: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> None:
    await LobbyService(db).leave(lobby_id, player.id)


@router.post("/{lobby_id}/ready", response_model=LobbyMemberResponse)
async def set_ready(
    lobby_id: str,
    body: ReadyUpdate,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> LobbyMemberResponse:
    member = await LobbyService(db).set_ready(lobby_id, player.id, body.ready)
    return LobbyMemberResponse.model_validate(member, from_attributes=True)


@router.post("/{lobby_id}/teams", response_model=TeamResponse, status_code=201)
async def open_team(
    lobby_id: str,
    body: TeamCreate,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    team = await LobbyService(db).create_team(lobby_id, body.code, body.name, player.id)
    return TeamResponse.model_validate(team, from_attributes=True)


@router.delete("/teams/{team_id}/members", status_code=204)
async def leave_team(
    team_id: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> None:
    await LobbyService(db).leave_team(team_id, player.id)


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse, status_code=201)
async def join_team(
    team_id: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    member = await LobbyService(db).join_team(team_id, player.id)
    return TeamMemberResponse.model_validate(member, from_attributes=True)

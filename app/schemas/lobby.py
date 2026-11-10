"""Lobby responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LobbyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    status: str
    max_players: int
    current_players: int
    created_at: datetime
    closed_at: datetime | None = None


class LobbyMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lobby_id: str
    player_id: str
    joined_at: datetime
    ready: bool


class ReadyUpdate(BaseModel):
    ready: bool


class LobbyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=36)
    max_players: int = Field(ge=1, le=100)
    game_mode_id: str | None = None


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    lobby_id: str
    player_id: str


class TeamCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=40)


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lobby_id: str
    code: str
    name: str

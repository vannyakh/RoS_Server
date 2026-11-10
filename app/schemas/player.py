"""Public player profile."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlayerProfile(BaseModel):
    id: str
    username: str
    is_active: bool
    kills: int = 0
    wins: int = 0
    matches_played: int = 0
    player_id: str | None = None
    nickname: str | None = None
    level: int = 1


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    nickname: str
    avatar_id: str | None = None
    level: int
    experience: int
    status: str
    created_at: datetime
    updated_at: datetime


class PlayerStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: str
    total_matches: int
    total_wins: int
    total_kills: int
    total_deaths: int
    total_playtime_seconds: int
    updated_at: datetime


class PlayerUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=3, max_length=32)
    avatar_id: str | None = None

"""Stored match responses. Live coordinates are not included."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MatchSummary(BaseModel):
    match_id: str
    status: str
    player_ids: list[str] = Field(default_factory=list)
    alive: int = 0
    winner_id: str | None = None


class MatchList(BaseModel):
    matches: list[MatchSummary] = Field(default_factory=list)


class MatchRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    match_code: str
    status: str
    max_players: int
    current_players: int
    game_mode_id: str | None = None
    map_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime


class MatchResultCreate(BaseModel):
    player_id: str
    placement: int = Field(ge=1)
    kills: int = Field(default=0, ge=0)
    score: int = Field(default=0, ge=0)
    rewards: dict = Field(default_factory=dict)

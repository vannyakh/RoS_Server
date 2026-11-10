"""Reference-data responses. The metadata column is exposed as details."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str
    details: dict = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ItemDefinitionResponse(DefinitionResponse):
    category: str
    max_stack: int


class GameModeResponse(DefinitionResponse):
    team_size: int
    min_players: int
    max_players: int


class MapDefinitionResponse(DefinitionResponse):
    width: int
    height: int

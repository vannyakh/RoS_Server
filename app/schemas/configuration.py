"""Configuration responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    config_key: str
    value: dict
    version: int
    updated_at: datetime


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    enabled: bool
    value: dict
    version: int
    updated_at: datetime


class ConfigurationUpdate(BaseModel):
    value: dict
    note: str | None = Field(default=None, max_length=200)

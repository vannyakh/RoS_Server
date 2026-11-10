"""Inventory responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_definition_id: str
    quantity: int
    updated_at: datetime


class InventoryResponse(BaseModel):
    id: str | None = None
    player_id: str
    items: list[InventoryItemResponse] = Field(default_factory=list)
    currencies: list["CurrencyResponse"] = Field(default_factory=list)


class CurrencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency_code: str
    balance: int


class CurrencyChange(BaseModel):
    currency_code: str = Field(min_length=1, max_length=16)
    amount: int
    reason: str = Field(min_length=1, max_length=64)


class ItemQuantityChange(BaseModel):
    item_code: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1)


InventoryResponse.model_rebuild()

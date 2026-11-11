"""Wallet and skin responses."""

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    coin: int = 0
    diamond: int = 0
    equipped_skin: str | None = None
    owned_skins: list[str] = Field(default_factory=list)


class SkinResponse(BaseModel):
    code: str
    name: str
    currency: str | None = None
    price: int
    owned: bool
    equipped: bool

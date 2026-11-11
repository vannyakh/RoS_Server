"""Coin, diamond, and skin routes for the signed-in player."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player
from app.infrastructure.database import get_db
from app.models.player import Player
from app.schemas.cosmetics import SkinResponse, WalletResponse
from app.services.cosmetics_service import equip_skin, purchase_skin, skin_catalog, wallet_snapshot

router = APIRouter(prefix="/cosmetics", tags=["Cosmetics"])


@router.get("/wallet", response_model=WalletResponse)
async def wallet(
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    return WalletResponse.model_validate(await wallet_snapshot(db, player))


@router.get("/skins", response_model=list[SkinResponse])
async def skins(
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[SkinResponse]:
    return [SkinResponse.model_validate(row) for row in await skin_catalog(db, player)]


@router.post("/skins/{code}/purchase", response_model=WalletResponse)
async def purchase(
    code: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    return WalletResponse.model_validate(await purchase_skin(db, player, code))


@router.post("/skins/{code}/equip", response_model=WalletResponse)
async def equip(
    code: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    return WalletResponse.model_validate(await equip_skin(db, player, code))

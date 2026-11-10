"""Authenticated player profile."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_account
from app.infrastructure.database import get_db
from app.models.account import Account
from app.schemas.player import PlayerProfile
from app.services.player_service import profile_for_account

router = APIRouter(prefix="/players", tags=["Players"])


@router.get("/me", response_model=PlayerProfile)
async def me(
    account: Account = Depends(current_account),
    db: AsyncSession = Depends(get_db),
) -> PlayerProfile:
    return await profile_for_account(db, account)

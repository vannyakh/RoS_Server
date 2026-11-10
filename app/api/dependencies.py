"""Shared API dependencies."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.infrastructure.database import get_db
from app.models.account import Account
from app.models.player import Player
from app.repositories.player_repository import PlayerRepository
from app.services.account_service import AccountService

bearer = HTTPBearer()


async def current_account(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Account:
    return await AccountService(db).account_for_token(credentials.credentials)


async def current_player(
    account: Account = Depends(current_account),
    db: AsyncSession = Depends(get_db),
) -> Player:
    player = await PlayerRepository(db).by_account_id(account.id)
    if player is None or player.status != "active":
        raise AppError(401, "Player unavailable")
    return player

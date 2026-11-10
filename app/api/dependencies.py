"""Shared API dependencies."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.infrastructure.database import get_db
from app.models.account import Account
from app.models.player import Player
from app.repositories.account_repository import AccountRepository
from app.repositories.player_repository import PlayerRepository

bearer = HTTPBearer()


async def current_account(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Account:
    payload = decode_access_token(credentials.credentials)
    account_id = payload.get("sub")
    if not account_id:
        raise AppError(401, "Invalid or expired token")
    account = await AccountRepository(db).by_id(account_id)
    if account is None or account.status != "active":
        raise AppError(401, "Player unavailable")
    return account


async def current_player(
    account: Account = Depends(current_account),
    db: AsyncSession = Depends(get_db),
) -> Player:
    player = await PlayerRepository(db).by_account_id(account.id)
    if player is None or player.status != "active":
        raise AppError(401, "Player unavailable")
    return player

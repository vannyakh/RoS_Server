"""Account registration and login."""

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import bearer, current_account
from app.infrastructure.database import get_db
from app.models.account import Account
from app.schemas.auth import LoginRequest, PlayerCreated, RegisterRequest, TokenResponse
from app.services.auth_service import login_player, logout_player, register_player

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=PlayerCreated, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)) -> PlayerCreated:
    player = await register_player(db, data.username, data.password)
    return PlayerCreated(id=player.id, username=player.username)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    host = request.client.host if request.client else "unknown"
    return await login_player(db, data.username, data.password, host)


@router.post("/logout", status_code=204)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    account: Account = Depends(current_account),
    db: AsyncSession = Depends(get_db),
) -> None:
    await logout_player(db, account, credentials.credentials)

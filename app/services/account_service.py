"""Account registration and login. Passwords and token hashes never leave this layer."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, hash_token, token_expires_in, verify_password
from app.models.account import Account, AccountSession, LoginHistory
from app.models.player import Player, PlayerStatistics
from app.repositories.account_repository import AccountRepository
from app.repositories.player_repository import PlayerRepository
from app.schemas.auth import TokenResponse

_USERNAME = re.compile(r"^[a-z0-9_]{3,32}$")


def normalize_username(username: str) -> str:
    normalized = username.strip().casefold()
    if not _USERNAME.match(normalized):
        raise AppError(422, "Username must be 3-32 letters, numbers, or underscores")
    return normalized


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.players = PlayerRepository(session)

    async def register(self, username: str, password: str, email: str | None = None, *, commit: bool = True) -> Account:
        normalized = normalize_username(username)
        if await self.accounts.by_username(normalized) is not None:
            raise AppError(409, "Username already exists")
        account = Account(
            username=normalized,
            email=email.strip().casefold() if email else None,
            password_hash=hash_password(password),
            status="active",
            is_verified=False,
        )
        self.session.add(account)
        await self.session.flush()
        player = Player(account_id=account.id, nickname=normalized, status="active")
        self.session.add(player)
        await self.session.flush()
        self.session.add(PlayerStatistics(player_id=player.id))
        try:
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, "Username already exists") from exc
        if commit:
            await self.session.refresh(account)
        return account

    async def login(self, username: str, password: str, ip_address: str | None) -> TokenResponse:
        normalized = username.strip().casefold()
        account = await self.accounts.by_username(normalized)
        if account is None or not verify_password(password, account.password_hash):
            await self._record(account.id if account else None, "failure", ip_address)
            await self.session.commit()
            raise AppError(401, "Invalid username or password")
        if account.status != "active":
            await self._record(account.id, "failure", ip_address)
            await self.session.commit()
            raise AppError(401, "Invalid username or password")
        token = create_access_token(account.id)
        now = datetime.now(timezone.utc)
        account.last_login_at = now
        self.session.add(
            AccountSession(
                account_id=account.id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(minutes=settings.jwt_expire_minutes),
            )
        )
        await self._record(account.id, "success", ip_address)
        await self.session.commit()
        return TokenResponse(access_token=token, expires_in=token_expires_in())

    async def _record(self, account_id: str | None, status: str, ip_address: str | None) -> None:
        await self.accounts.add_login(
            LoginHistory(account_id=account_id, login_status=status, ip_address=ip_address)
        )

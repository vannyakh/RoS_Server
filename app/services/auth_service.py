"""Login rate limit and the HTTP-facing account calls."""

from time import monotonic

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.schemas.auth import TokenResponse
from app.services.account_service import AccountService, normalize_username

_WINDOW_SECONDS = 60.0
_MAX_FAILURES = 5
_failures: dict[str, list[float]] = {}


def _prune(host: str) -> list[float]:
    now = monotonic()
    recent = [stamp for stamp in _failures.get(host, []) if now - stamp < _WINDOW_SECONDS]
    _failures[host] = recent
    return recent


def too_many_attempts(host: str) -> bool:
    return len(_prune(host)) >= _MAX_FAILURES


def record_failure(host: str) -> None:
    _prune(host).append(monotonic())


def clear_failures(host: str) -> None:
    _failures.pop(host, None)


async def register_player(db: AsyncSession, username: str, password: str) -> Account:
    return await AccountService(db).register(username, password)


async def logout_player(db: AsyncSession, account: Account, token: str) -> None:
    await AccountService(db).revoke_token(account.id, token)


async def login_player(db: AsyncSession, username: str, password: str, host: str) -> TokenResponse:
    if too_many_attempts(host):
        raise AppError(429, "Too many login attempts")
    try:
        token = await AccountService(db).login(username, password, host)
    except AppError:
        record_failure(host)
        raise
    clear_failures(host)
    return token


__all__ = [
    "clear_failures",
    "login_player",
    "logout_player",
    "normalize_username",
    "record_failure",
    "register_player",
    "too_many_attempts",
]

"""Profile reads. The public id stays the account id used by existing tokens."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.repositories.player_repository import PlayerRepository
from app.schemas.player import PlayerProfile


async def profile_for_account(session: AsyncSession, account: Account) -> PlayerProfile:
    repository = PlayerRepository(session)
    player = await repository.by_account_id(account.id)
    statistics = await repository.statistics_for_account(account.id)
    return PlayerProfile(
        id=account.id,
        username=account.username,
        is_active=account.is_active,
        kills=statistics.total_kills if statistics else 0,
        wins=statistics.total_wins if statistics else 0,
        matches_played=statistics.total_matches if statistics else 0,
        player_id=player.id if player else None,
        nickname=player.nickname if player else account.username,
        level=player.level if player else 1,
    )

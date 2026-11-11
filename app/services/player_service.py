"""Profile reads and the fields a player may change. The public id stays the account id."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.repositories.player_repository import PlayerRepository
from app.schemas.player import PlayerProfile, PlayerUpdate
from app.services.account_service import normalize_username
from app.services.cosmetics_service import wallet_snapshot


async def update_profile(session: AsyncSession, account: Account, data: PlayerUpdate) -> PlayerProfile:
    repository = PlayerRepository(session)
    player = await repository.by_account_id(account.id)
    if player is None or player.status != "active":
        raise AppError(401, "Player unavailable")
    changed = False
    if "nickname" in data.model_fields_set and data.nickname is not None:
        nickname = normalize_username(data.nickname)
        if nickname != player.nickname:
            taken = await repository.by_nickname(nickname)
            if taken is not None and taken.id != player.id:
                raise AppError(409, "Nickname already exists")
            player.nickname = nickname
            changed = True
    if "avatar_id" in data.model_fields_set:
        avatar = data.avatar_id.strip() if isinstance(data.avatar_id, str) else None
        avatar = avatar or None
        if avatar != player.avatar_id:
            player.avatar_id = avatar
            changed = True
    if changed:
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise AppError(409, "Nickname already exists") from exc
    return await profile_for_account(session, account)


async def profile_for_account(session: AsyncSession, account: Account) -> PlayerProfile:
    repository = PlayerRepository(session)
    player = await repository.by_account_id(account.id)
    statistics = await repository.statistics_for_account(account.id)
    wallet = await wallet_snapshot(session, player) if player is not None else {}
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
        coin=wallet.get("coin", 0),
        diamond=wallet.get("diamond", 0),
        equipped_skin=wallet.get("equipped_skin"),
        owned_skins=wallet.get("owned_skins", []),
    )

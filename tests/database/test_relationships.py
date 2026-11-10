"""Account and profile rows stay linked."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.player import Player
from app.services.account_service import AccountService


async def test_registration_creates_profile_and_statistics(db_session):
    account = await AccountService(db_session).register("linked_user", "StrongTestPassword123!")
    stored = await db_session.scalar(
        select(Account)
        .where(Account.id == account.id)
        .options(selectinload(Account.player).selectinload(Player.statistics))
    )
    assert stored.player is not None
    assert stored.player.nickname == "linked_user"
    assert stored.player.statistics.total_matches == 0

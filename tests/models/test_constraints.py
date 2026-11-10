"""Constraints that the database itself must enforce."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.player import Player
from app.services.account_service import AccountService
from app.services.inventory_service import InventoryService


async def test_account_username_is_unique(db_session):
    service = AccountService(db_session)
    await service.register("Alpha_One", "StrongTestPassword123!")
    with pytest.raises(Exception):
        await service.register("alpha_one", "StrongTestPassword123!")


async def test_player_requires_an_account(db_session):
    db_session.add(Player(account_id="missing-account", nickname="ghost", status="active"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_currency_balance_cannot_be_negative(db_session):
    account = await AccountService(db_session).register("banker", "StrongTestPassword123!")
    from app.repositories.player_repository import PlayerRepository

    player = await PlayerRepository(db_session).by_account_id(account.id)
    service = InventoryService(db_session)
    with pytest.raises(Exception) as caught:
        await service.apply_currency(player.id, "SOFT", -5, "spend")
    assert "Insufficient balance" in str(caught.value)


async def test_match_participant_is_unique(db_session):
    from app.repositories.player_repository import PlayerRepository
    from app.services.match_service import MatchService

    account = await AccountService(db_session).register("fighter", "StrongTestPassword123!")
    player = await PlayerRepository(db_session).by_account_id(account.id)
    matches = MatchService(db_session)
    match = await matches.create("match-unique", 8)
    await matches.add_participant(match.id, player.id)
    with pytest.raises(Exception) as caught:
        await matches.add_participant(match.id, player.id)
    assert "already in the match" in str(caught.value)

"""Repository and service behavior for accounts, lobbies, and stored matches."""

import pytest

from app.repositories.account_repository import AccountRepository
from app.repositories.player_repository import PlayerRepository
from app.services.account_service import AccountService
from app.services.lobby_service import LobbyService
from app.services.match_service import MatchService


async def test_account_repository_finds_the_normalized_username(db_session):
    created = await AccountService(db_session).register("Repo_User", "StrongTestPassword123!")
    found = await AccountRepository(db_session).by_username("repo_user")
    assert found is not None
    assert found.id == created.id
    assert found.password_hash != "StrongTestPassword123!"


async def test_lobby_rejects_a_second_membership_and_a_full_room(db_session):
    first = await AccountService(db_session).register("lobby_one", "StrongTestPassword123!")
    second = await AccountService(db_session).register("lobby_two", "StrongTestPassword123!")
    players = PlayerRepository(db_session)
    first_player = await players.by_account_id(first.id)
    second_player = await players.by_account_id(second.id)
    lobbies = LobbyService(db_session)
    lobby = await lobbies.open_lobby("room", max_players=1)
    await lobbies.join(lobby.id, first_player.id)
    with pytest.raises(Exception) as duplicate:
        await lobbies.join(lobby.id, first_player.id)
    with pytest.raises(Exception) as full:
        await lobbies.join(lobby.id, second_player.id)
    assert "already" in str(duplicate.value)
    assert "full" in str(full.value)


async def test_match_result_is_stored_in_one_transaction(db_session):
    account = await AccountService(db_session).register("result_user", "StrongTestPassword123!")
    player = await PlayerRepository(db_session).by_account_id(account.id)
    matches = MatchService(db_session)
    match = await matches.create("stored-match", 4)
    await matches.add_participant(match.id, player.id)
    await matches.transition(match.id, "lobby")
    await matches.transition(match.id, "running")
    finished = await matches.finalize(match.id, [{"player_id": player.id, "placement": 1, "kills": 2, "score": 10}])
    assert finished.status == "completed"
    with pytest.raises(Exception) as caught:
        await matches.transition(finished.id, "running")
    assert "Invalid match transition" in str(caught.value)

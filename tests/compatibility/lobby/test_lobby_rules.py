import pytest

from tools.game_simulator import SimulatedLobby, SimulatedPlayer


def test_lobby_capacity_ready_and_team_rules():
    lobby = SimulatedLobby(code="ROOM", max_players=1)
    first = SimulatedPlayer("one")
    second = SimulatedPlayer("two")
    first.authenticate("CompatPassword123!")
    second.authenticate("CompatPassword123!")
    lobby.join(first)
    with pytest.raises(RuntimeError, match="full"):
        lobby.join(second)
    lobby.max_players = 2
    lobby.join(second)
    team = lobby.create_team("A")
    lobby.join_team(team, first)
    with pytest.raises(RuntimeError, match="already on a team"):
        lobby.join_team(team, first)
    lobby.set_ready(first, True)
    assert first.player_id in lobby.ready

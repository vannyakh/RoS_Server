from tools.player_simulator import login, profile, register


async def test_profile_reports_nickname_and_level(client):
    assert (await register(client, "profile_user", "CompatPassword123!")).status_code == 201
    token = (await login(client, "profile_user", "CompatPassword123!")).json()["access_token"]
    body = (await profile(client, token)).json()
    assert body["nickname"] == "profile_user"
    assert body["level"] == 1
    assert body["matches_played"] == 0
    assert "password_hash" not in body

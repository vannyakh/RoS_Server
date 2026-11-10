"""Match results are stored on the player row after the tick."""

PASSWORD = "StrongTestPassword123!"


async def test_saved_match_updates_the_profile(client):
    from app.services.persistence_service import persistence_service

    created = await client.post(
        "/api/v1/auth/register",
        json={"username": "match_hero", "password": PASSWORD},
    )
    assert created.status_code == 201
    await persistence_service.save_player_progress(created.json()["id"], {"kills": 3, "win": True})
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "match_hero", "password": PASSWORD},
    )
    profile = await client.get(
        "/api/v1/players/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    body = profile.json()
    assert body["kills"] == 3
    assert body["wins"] == 1
    assert body["matches_played"] == 1

    missing = await client.get("/api/v1/matches/does-not-exist")
    assert missing.status_code == 404


async def test_lobby_shows_a_queued_player(client):
    from app.game.engine import game_engine

    await game_engine.join_queue("solo-http")
    lobby = (await client.get("/api/v1/lobby")).json()
    matches = (await client.get("/api/v1/matches")).json()
    in_lobby = any(player["player_id"] == "solo-http" for player in lobby["players"])
    in_match = any("solo-http" in match["player_ids"] for match in matches["matches"])
    assert in_lobby or in_match

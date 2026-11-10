"""Registration, login, and profile retrieval."""

PASSWORD = "StrongTestPassword123!"


async def test_register_login_and_profile(client):
    created = await client.post(
        "/api/v1/auth/register",
        json={"username": "Test_Player", "password": PASSWORD},
    )
    assert created.status_code == 201
    assert created.json()["username"] == "test_player"
    assert "password" not in created.json()

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"username": "test_player", "password": PASSWORD},
    )
    assert duplicate.status_code == 409

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "TEST_PLAYER", "password": PASSWORD},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600

    profile = await client.get(
        "/api/v1/players/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["username"] == "test_player"
    assert "password_hash" not in profile.json()

    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/api/v1/lobby")).json()["players"] == []
    assert (await client.get("/api/v1/matches")).json()["matches"] == []


async def test_invalid_login(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "missing", "password": "not-a-real-password"},
    )
    assert response.status_code == 401


async def test_short_password_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "shortpw", "password": "too-short"},
    )
    assert response.status_code == 422

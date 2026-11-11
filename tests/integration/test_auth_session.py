"""Session issue, rejection, expiry, and logout."""

from datetime import datetime, timedelta, timezone

import jwt

PASSWORD = "StrongTestPassword123!"


async def _login(client, username: str) -> str:
    created = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert created.status_code == 201
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_logout_revokes_only_that_session(client):
    first = await _login(client, "session_one")
    second = await client.post(
        "/api/v1/auth/login",
        json={"username": "session_one", "password": PASSWORD},
    )
    assert second.status_code == 200
    other = second.json()["access_token"]

    assert (await client.get("/api/v1/players/me", headers=_headers(first))).status_code == 200
    logged_out = await client.post("/api/v1/auth/logout", headers=_headers(first))
    assert logged_out.status_code == 204
    assert (await client.get("/api/v1/players/me", headers=_headers(first))).status_code == 401
    assert (await client.get("/api/v1/players/me", headers=_headers(other))).status_code == 200
    again = await client.post("/api/v1/auth/logout", headers=_headers(first))
    assert again.status_code == 401


async def test_token_without_a_session_row_is_rejected(client):
    from app.core.config import settings

    token = await _login(client, "session_two")
    profile = await client.get("/api/v1/players/me", headers=_headers(token))
    account_id = profile.json()["id"]
    now = datetime.now(timezone.utc)
    unsigned = jwt.encode(
        {"sub": account_id, "iat": now, "exp": now + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    rejected = await client.get("/api/v1/players/me", headers=_headers(unsigned))
    assert rejected.status_code == 401


async def test_missing_token_is_rejected(client):
    response = await client.get("/api/v1/players/me")
    assert response.status_code == 401


async def test_expired_session_row_is_rejected(client):
    from sqlalchemy import update

    from app.core.security import hash_token
    from app.infrastructure.database import SessionLocal
    from app.models.account import AccountSession

    token = await _login(client, "session_row_expired")
    assert (await client.get("/api/v1/players/me", headers=_headers(token))).status_code == 200
    async with SessionLocal() as session:
        await session.execute(
            update(AccountSession)
            .where(AccountSession.token_hash == hash_token(token))
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=5))
        )
        await session.commit()
    rejected = await client.get("/api/v1/players/me", headers=_headers(token))
    assert rejected.status_code == 401


async def test_expired_jwt_is_rejected(client):
    from app.core.config import settings

    token = await _login(client, "session_three")
    profile = await client.get("/api/v1/players/me", headers=_headers(token))
    account_id = profile.json()["id"]
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": account_id, "iat": now - timedelta(minutes=10), "exp": now - timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    rejected = await client.get("/api/v1/players/me", headers=_headers(expired))
    assert rejected.status_code == 401

"""Operator tokens refresh in place; the chain still ends at the maximum session length."""

from datetime import datetime, timedelta, timezone

PASSWORD = "StrongTestPassword123!"


async def _login(client, username: str = "refresh_admin") -> dict:
    from app.infrastructure.database import SessionLocal
    from app.services.operator_service import OperatorService

    async with SessionLocal() as session:
        await OperatorService(session).create_operator(username, PASSWORD, ["support"], audit=False)
    response = await client.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_refresh_rotates_with_a_short_grace_for_the_old_token(client):
    from sqlalchemy import select

    from app.core.security import hash_token
    from app.infrastructure.database import SessionLocal
    from app.models.operator import OperatorSession

    first = await _login(client)
    assert first["session_expires_at"]

    refreshed = await client.post("/api/v1/admin/auth/refresh", headers=_auth(first["access_token"]))
    assert refreshed.status_code == 200, refreshed.text
    second = refreshed.json()
    assert second["access_token"] != first["access_token"]
    assert second["session_expires_at"] == first["session_expires_at"]
    assert (await client.get("/api/v1/admin/me", headers=_auth(second["access_token"]))).status_code == 200

    # Old token: still accepted inside the grace window, refused once it passes.
    assert (await client.get("/api/v1/admin/me", headers=_auth(first["access_token"]))).status_code == 200
    async with SessionLocal() as session:
        old = await session.scalar(select(OperatorSession).where(OperatorSession.token_hash == hash_token(first["access_token"])))
        old.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()
    assert (await client.get("/api/v1/admin/me", headers=_auth(first["access_token"]))).status_code == 401
    assert (await client.post("/api/v1/admin/auth/refresh", headers=_auth(first["access_token"]))).status_code == 401


async def test_refresh_stops_at_the_maximum_session_length(client):
    from sqlalchemy import select

    from app.core.security import hash_token
    from app.infrastructure.database import SessionLocal
    from app.models.operator import OperatorSession

    first = await _login(client, "capped_admin")
    async with SessionLocal() as session:
        row = await session.scalar(select(OperatorSession).where(OperatorSession.token_hash == hash_token(first["access_token"])))
        row.started_at = datetime.now(timezone.utc) - timedelta(hours=13)
        await session.commit()
    ended = await client.post("/api/v1/admin/auth/refresh", headers=_auth(first["access_token"]))
    assert ended.status_code == 401
    assert "maximum length" in ended.json()["detail"]


async def test_refresh_never_outlives_the_chain(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "operator_session_max_hours", 1)
    monkeypatch.setattr(settings, "jwt_expire_minutes", 120)
    first = await _login(client, "short_chain_admin")
    assert first["expires_in"] <= 3600


async def test_refresh_refuses_player_revoked_and_missing_tokens(client):
    await client.post("/api/v1/auth/register", json={"username": "refresh_player", "password": PASSWORD})
    player = (await client.post("/api/v1/auth/login", json={"username": "refresh_player", "password": PASSWORD})).json()
    assert (await client.post("/api/v1/admin/auth/refresh", headers=_auth(player["access_token"]))).status_code == 401
    assert (await client.post("/api/v1/admin/auth/refresh")).status_code in (401, 403)

    operator = await _login(client, "revoked_admin")
    assert (await client.post("/api/v1/admin/auth/logout", headers=_auth(operator["access_token"]))).status_code == 204
    assert (await client.post("/api/v1/admin/auth/refresh", headers=_auth(operator["access_token"]))).status_code == 401

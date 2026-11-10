"""PostgreSQL coverage.

The JSONB assertion only checks the compiled dialect. A live server test runs when
POSTGRES_TEST_URL is set. SQLite success does not imply that URL was exercised.
"""

import os

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models.game_data import ItemDefinition


def test_postgresql_dialect_uses_jsonb():
    sql = str(CreateTable(ItemDefinition.__table__).compile(dialect=postgresql.dialect()))
    assert "JSONB" in sql


@pytest.mark.asyncio
async def test_postgres_account_roundtrip(monkeypatch):
    url = os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not set, so PostgreSQL was not executed")
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.services.account_service import AccountService

    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_async_engine(url)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            account = await AccountService(session).register("pg_roundtrip", "StrongTestPassword123!")
            assert account.username == "pg_roundtrip"
            found = await session.scalar(text("SELECT username FROM accounts WHERE id = :id"), {"id": account.id})
            assert found == "pg_roundtrip"
            await session.execute(text("DELETE FROM player_statistics WHERE player_id IN (SELECT id FROM players WHERE account_id = :id)"), {"id": account.id})
            await session.execute(text("DELETE FROM players WHERE account_id = :id"), {"id": account.id})
            await session.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account.id})
            await session.commit()
    finally:
        await engine.dispose()

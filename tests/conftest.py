"""Test environment. These values are set before the application is imported."""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_ros.db"
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-pytest-is-long-enough-for-hs256")
os.environ.setdefault("APP_ENV", "development")
os.environ["DEBUG"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def reset_engine():
    from app.game.engine import game_engine

    game_engine.reset_state()
    yield


@pytest.fixture
async def db_session():
    import app.models  # noqa: F401
    from app.infrastructure.database import Base, SessionLocal, engine, init_db

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        await connection.exec_driver_sql("DROP TABLE IF EXISTS legacy_players")
    await init_db()
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client():
    from app.game.engine import game_engine
    from app.infrastructure.database import Base, engine
    from app.main import app
    from app.services import auth_service

    auth_service._failures.clear()
    game_engine.reset_state()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        await connection.exec_driver_sql("DROP TABLE IF EXISTS legacy_players")

    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http

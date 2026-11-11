"""Async SQLAlchemy engine and session factory."""

import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.observability.metrics import install_query_metrics

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _engine_options() -> dict:
    if settings.database_url.startswith("sqlite"):
        # timeout is sqlite3's busy wait, in seconds. Concurrent lobby joins must wait
        # for the writer instead of failing the request immediately.
        return {"poolclass": NullPool, "connect_args": {"timeout": 5}}
    return {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}


engine = create_async_engine(settings.database_url, echo=settings.debug, **_engine_options())
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
install_query_metrics(engine)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _upgrade_database() -> None:
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("alembic upgrade head failed during startup")


async def init_db() -> None:
    """Apply reviewed Alembic revisions. Production should run `alembic upgrade head` itself."""

    if settings.app_env != "development":
        return
    await asyncio.to_thread(_upgrade_database)


async def close_db() -> None:
    await engine.dispose()

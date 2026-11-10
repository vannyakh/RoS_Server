"""Alembic upgrade and downgrade on disposable SQLite files."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _config() -> Config:
    return Config(str(Path("alembic.ini").resolve()))


def test_upgrade_and_downgrade_on_an_empty_database(tmp_path, monkeypatch):
    url = "sqlite+aiosqlite:///" + (tmp_path / "empty.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config()
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine("sqlite:///" + (tmp_path / "empty.db").as_posix())
    with engine.connect() as connection:
        tables = set(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    assert "accounts" in tables
    assert "players" in tables


def test_legacy_players_are_copied_and_kept(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE players (
            id VARCHAR(36) PRIMARY KEY,
            username VARCHAR(32) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL,
            kills INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            matches_played INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        "INSERT INTO players VALUES ('acct-1', 'old_name', 'hash', 1, 4, 2, 3)"
    )
    connection.commit()
    connection.close()

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///" + database.as_posix())
    command.upgrade(_config(), "head")

    engine = create_engine("sqlite:///" + database.as_posix())
    with engine.connect() as connection:
        account = connection.execute(text("SELECT username, status FROM accounts WHERE id = 'acct-1'")).one()
        stats = connection.execute(
            text(
                """
                SELECT total_kills, total_wins, total_matches
                FROM player_statistics
                JOIN players ON players.id = player_statistics.player_id
                WHERE players.account_id = 'acct-1'
                """
            )
        ).one()
        legacy = connection.execute(text("SELECT username FROM legacy_players")).one()
    assert account == ("old_name", "active")
    assert stats == (4, 2, 3)
    assert legacy == ("old_name",)

    command.downgrade(_config(), "base")
    engine = create_engine("sqlite:///" + database.as_posix())
    with engine.connect() as connection:
        restored = connection.execute(text("SELECT username, kills FROM players")).one()
        tables = set(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    assert restored == ("old_name", 4)
    assert "accounts" not in tables

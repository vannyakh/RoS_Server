"""Preserve the pre-account players table. Upgrade renames it and copies rows; it does not delete them."""

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa


def preserve_legacy_players(connection) -> None:
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "players" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("players")}
    if "password_hash" in columns and "account_id" not in columns:
        connection.execute(sa.text("ALTER TABLE players RENAME TO legacy_players"))


def copy_legacy_players(connection) -> None:
    inspector = sa.inspect(connection)
    if "legacy_players" not in set(inspector.get_table_names()):
        return
    rows = connection.execute(
        sa.text(
            "SELECT id, username, password_hash, is_active, kills, wins, matches_played FROM legacy_players"
        )
    ).mappings()
    now = datetime.now(timezone.utc)
    for row in rows:
        exists = connection.execute(
            sa.text("SELECT id FROM accounts WHERE id = :id"),
            {"id": row["id"]},
        ).first()
        if exists is not None:
            continue
        status = "active" if row["is_active"] in (1, True, "1") else "suspended"
        connection.execute(
            sa.text(
                """
                INSERT INTO accounts
                    (id, username, email, password_hash, status, is_verified, created_at, updated_at, last_login_at)
                VALUES
                    (:id, :username, NULL, :password_hash, :status, :verified, :now, :now, NULL)
                """
            ),
            {
                "id": row["id"],
                "username": row["username"],
                "password_hash": row["password_hash"],
                "status": status,
                "verified": False,
                "now": now,
            },
        )
        player_id = str(uuid4())
        connection.execute(
            sa.text(
                """
                INSERT INTO players
                    (id, account_id, nickname, avatar_id, level, experience, status, created_at, updated_at)
                VALUES
                    (:id, :account_id, :nickname, NULL, 1, 0, 'active', :now, :now)
                """
            ),
            {"id": player_id, "account_id": row["id"], "nickname": row["username"], "now": now},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO player_statistics
                    (id, player_id, total_matches, total_wins, total_kills, total_deaths,
                     total_playtime_seconds, updated_at)
                VALUES
                    (:id, :player_id, :matches, :wins, :kills, 0, 0, :now)
                """
            ),
            {
                "id": str(uuid4()),
                "player_id": player_id,
                "matches": int(row["matches_played"] or 0),
                "wins": int(row["wins"] or 0),
                "kills": int(row["kills"] or 0),
                "now": now,
            },
        )


def restore_legacy_players(connection) -> None:
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if "legacy_players" in tables and "players" not in tables:
        connection.execute(sa.text("ALTER TABLE legacy_players RENAME TO players"))

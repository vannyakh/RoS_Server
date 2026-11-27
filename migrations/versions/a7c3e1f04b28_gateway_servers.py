"""gateway servers (original-client gateway processes on the server-select screen)

Revision ID: a7c3e1f04b28
Revises: d1e5b7a3c920
Create Date: 2026-11-27 11:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e1f04b28"
down_revision: Union[str, Sequence[str], None] = "d1e5b7a3c920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gateway_servers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("server_key", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("host", sa.String(length=253), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("zone", sa.Integer(), server_default="1", nullable=False),
        sa.Column("group_id", sa.Integer(), server_default="10001", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="auto", nullable=False),
        sa.Column("capacity", sa.Integer(), server_default="100", nullable=False),
        sa.Column("listed", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.String(length=64), server_default="", nullable=False),
        sa.Column("players_online", sa.Integer(), server_default="0", nullable=False),
        sa.Column("players_in_match", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_key", name="uq_gateway_servers_key"),
        sa.CheckConstraint("status IN ('auto', 'smooth', 'busy', 'full', 'maintenance')", name=op.f("ck_gateway_servers_status")),
        sa.CheckConstraint("capacity >= 1", name=op.f("ck_gateway_servers_capacity")),
        sa.CheckConstraint("port >= 1 AND port <= 65535", name=op.f("ck_gateway_servers_port")),
        sa.CheckConstraint("players_online >= 0 AND players_in_match >= 0", name=op.f("ck_gateway_servers_players")),
    )


def downgrade() -> None:
    op.drop_table("gateway_servers")

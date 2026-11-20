"""game asset library: display images looked up by kind and key

Revision ID: d2f7a1c9e044
Revises: c6e1d84f2a37
Create Date: 2026-11-20 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2f7a1c9e044"
down_revision: Union[str, Sequence[str], None] = "c6e1d84f2a37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "kind IN ('rank', 'prop', 'item', 'character', 'currency', 'badge', 'other')", name=op.f("ck_game_assets_kind")
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_game_assets_size_bytes")),
        sa.ForeignKeyConstraint(["uploaded_by"], ["operators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "key", name="uq_game_assets_kind_key"),
    )
    op.create_index("ix_game_assets_sha256", "game_assets", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_game_assets_sha256", table_name="game_assets")
    op.drop_table("game_assets")

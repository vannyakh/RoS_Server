"""per-player mail

Revision ID: c7a1f4e9b2d6
Revises: b5d8f2a60c37
Create Date: 2026-11-26 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c7a1f4e9b2d6"
down_revision: Union[str, Sequence[str], None] = "b5d8f2a60c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "player_mails",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("sender", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("props", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_player_mails_account_id_accounts", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_id"], ["operators.id"], name="fk_player_mails_operator_id_operators", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_player_mails"),
        sa.UniqueConstraint("number", name="uq_player_mails_number"),
    )
    op.create_index("ix_player_mails_account_id", "player_mails", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_player_mails_account_id", table_name="player_mails")
    op.drop_table("player_mails")

"""gateway player profile: battle records, credit, rank score, space likes

Revision ID: b3d9f17c5e20
Revises: a7c4e2b9d315
Create Date: 2026-11-19 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d9f17c5e20"
down_revision: Union[str, Sequence[str], None] = "a7c4e2b9d315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COUNTERS = (
    "fight_count", "win_count", "top5_count", "kill_count", "death_count", "assist_count",
    "head_shot_count", "hit_count", "fire_count", "fight_time_seconds", "collect_count", "heal_count",
    "max_round_kill", "max_round_assist", "max_round_heal", "max_kill_distance_dm",
    "max_move_distance_dm", "max_fight_time_seconds",
)


def upgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.add_column(sa.Column("rank_score", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("credit_score", sa.Integer(), nullable=False, server_default="100"))
        batch.add_column(sa.Column("credit_status_last_week", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("credit_weeks", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("credit_gifts", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("space_likes", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "gateway_battle_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("queue", sa.String(length=16), nullable=False),
        sa.Column("team_mode", sa.String(length=16), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in _COUNTERS[:6]],
        sa.Column("damage", sa.BigInteger(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in _COUNTERS[6:]],
        sa.CheckConstraint("season >= 0", name=op.f("ck_gateway_battle_records_season")),
        sa.CheckConstraint(
            "queue IN ('total', 'ranked', 'matching')", name=op.f("ck_gateway_battle_records_queue")
        ),
        sa.CheckConstraint(
            "team_mode IN ('overall', 'solo', 'dual', 'quad', 'five')",
            name=op.f("ck_gateway_battle_records_team_mode"),
        ),
        sa.CheckConstraint(
            "fight_count >= 0 AND win_count >= 0 AND top5_count >= 0 AND kill_count >= 0 AND death_count >= 0",
            name=op.f("ck_gateway_battle_records_counts"),
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["gateway_identities.id"],
            name=op.f("fk_gateway_battle_records_identity_id_gateway_identities"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateway_battle_records")),
        sa.UniqueConstraint("identity_id", "season", "queue", "team_mode", name="uq_gateway_battle_records_key"),
    )
    op.create_index(
        op.f("ix_gateway_battle_records_identity_id"), "gateway_battle_records", ["identity_id"], unique=False
    )

    op.create_table(
        "gateway_credit_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Integer(), nullable=False),
        sa.Column("score_after", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=128), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["gateway_identities.id"],
            name=op.f("fk_gateway_credit_records_identity_id_gateway_identities"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateway_credit_records")),
    )
    op.create_index(
        "ix_gateway_credit_records_identity_created",
        "gateway_credit_records",
        ["identity_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_gateway_credit_records_identity_created", table_name="gateway_credit_records")
    op.drop_table("gateway_credit_records")
    op.drop_index(op.f("ix_gateway_battle_records_identity_id"), table_name="gateway_battle_records")
    op.drop_table("gateway_battle_records")
    with op.batch_alter_table("gateway_identities") as batch:
        for name in ("space_likes", "credit_gifts", "credit_weeks", "credit_status_last_week", "credit_score", "rank_score"):
            batch.drop_column(name)

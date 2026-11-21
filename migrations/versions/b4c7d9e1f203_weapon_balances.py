"""weapon balances: per-weapon combat tuning

Revision ID: b4c7d9e1f203
Revises: a3b8e6d24c51
Create Date: 2026-11-20 20:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c7d9e1f203"
down_revision: Union[str, Sequence[str], None] = "a3b8e6d24c51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weapon_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("weapon_class", sa.String(16), nullable=False),
        sa.Column("damage", sa.Float, nullable=False),
        sa.Column("fire_rate", sa.Float, nullable=False),
        sa.Column("magazine", sa.Integer, nullable=False),
        sa.Column("reload_seconds", sa.Float, nullable=False),
        sa.Column("effective_range", sa.Float, nullable=False),
        sa.Column("max_range", sa.Float, nullable=False),
        sa.Column("falloff_percent", sa.Float, nullable=False),
        sa.Column("spread", sa.Float, nullable=False),
        sa.Column("recoil", sa.Float, nullable=False),
        sa.Column("head_multiplier", sa.Float, nullable=False),
        sa.Column("torso_multiplier", sa.Float, nullable=False),
        sa.Column("limb_multiplier", sa.Float, nullable=False),
        sa.Column("vehicle_damage", sa.Float, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name=op.f("uq_weapon_balances_code")),
        sa.CheckConstraint("weapon_class IN ('assault', 'smg', 'sniper', 'shotgun', 'pistol', 'melee')", name=op.f("ck_weapon_balances_weapon_class")),
        sa.CheckConstraint("damage > 0", name=op.f("ck_weapon_balances_damage")),
        sa.CheckConstraint("max_range >= effective_range", name=op.f("ck_weapon_balances_range_order")),
    )


def downgrade() -> None:
    op.drop_table("weapon_balances")

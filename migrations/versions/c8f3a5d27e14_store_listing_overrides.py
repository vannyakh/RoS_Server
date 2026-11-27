"""store listing overrides: operator price / on-sale control of lobby themes

Revision ID: c8f3a5d27e14
Revises: b5d8f2a60c37
Create Date: 2026-11-26 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8f3a5d27e14"
down_revision: Union[str, Sequence[str], None] = "b5d8f2a60c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_listing_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.Integer, nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("on_sale", sa.Boolean, nullable=False),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("item_id", name=op.f("uq_store_listing_overrides_item_id")),
        sa.CheckConstraint("category IN ('lobby_theme')", name=op.f("ck_store_listing_overrides_category")),
        sa.CheckConstraint("currency IN ('diamond', 'coin')", name=op.f("ck_store_listing_overrides_currency")),
        sa.CheckConstraint("price >= 0 AND price <= 1000000", name=op.f("ck_store_listing_overrides_price")),
    )


def downgrade() -> None:
    op.drop_table("store_listing_overrides")

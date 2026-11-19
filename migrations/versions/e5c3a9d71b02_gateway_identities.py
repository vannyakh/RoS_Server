"""original-client gateway identities

Revision ID: e5c3a9d71b02
Revises: d8f1a6c04e21
Create Date: 2026-11-19 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5c3a9d71b02"
down_revision: Union[str, Sequence[str], None] = "d8f1a6c04e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gateway_identities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("external_uid", sa.String(length=64), nullable=False),
        sa.Column("char_type", sa.Integer(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ip", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_gateway_identities_account_id_accounts", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_gateway_identities"),
        sa.UniqueConstraint("account_id", name="uq_gateway_identities_account_id"),
        sa.UniqueConstraint("external_uid", name="uq_gateway_identities_external_uid"),
    )


def downgrade() -> None:
    op.drop_table("gateway_identities")

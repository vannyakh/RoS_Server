"""gateway identity head frame (avatar frame appearance id)

Revision ID: a9e4c7b13d58
Revises: a6d2e8f31c45
Create Date: 2026-11-21 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9e4c7b13d58"
down_revision: Union[str, Sequence[str], None] = "a6d2e8f31c45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.add_column(sa.Column("head_frame", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.drop_column("head_frame")

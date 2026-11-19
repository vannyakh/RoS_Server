"""gateway identity portrait (uploaded avatar file id)

Revision ID: f2b7d4e90a13
Revises: e5c3a9d71b02
Create Date: 2026-11-19 08:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b7d4e90a13"
down_revision: Union[str, Sequence[str], None] = "e5c3a9d71b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.add_column(sa.Column("portrait", sa.String(length=128), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.drop_column("portrait")

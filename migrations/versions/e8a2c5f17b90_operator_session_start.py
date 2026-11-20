"""operator session chain start, for refresh with a maximum session length

Revision ID: e8a2c5f17b90
Revises: d2f7a1c9e044
Create Date: 2026-11-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8a2c5f17b90"
down_revision: Union[str, Sequence[str], None] = "d2f7a1c9e044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("operator_sessions") as batch:
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("operator_sessions") as batch:
        batch.drop_column("started_at")

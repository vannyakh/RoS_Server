"""login session details: source, device, client version, time zone, country

Revision ID: c6e1d84f2a37
Revises: b3d9f17c5e20
Create Date: 2026-11-19 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6e1d84f2a37"
down_revision: Union[str, Sequence[str], None] = "b3d9f17c5e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("login_history") as batch:
        batch.add_column(sa.Column("source", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("country", sa.String(length=2), nullable=True))
        batch.add_column(sa.Column("device_model", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("os_name", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("client_version", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("time_zone", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("language", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("user_agent", sa.String(length=256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("login_history") as batch:
        for name in ("user_agent", "language", "time_zone", "client_version", "os_name", "device_model", "country", "source"):
            batch.drop_column(name)

"""gateway identity national flag (country code shown on My Page)

Revision ID: a6d2e8f31c45
Revises: b4c7d9e1f203
Create Date: 2026-11-20 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6d2e8f31c45"
down_revision: Union[str, Sequence[str], None] = "b4c7d9e1f203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.add_column(sa.Column("national_flag", sa.String(length=8), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.drop_column("national_flag")

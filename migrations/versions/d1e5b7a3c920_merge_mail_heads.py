"""merge player_mails and gateway_mails heads

Revision ID: d1e5b7a3c920
Revises: c7a1f4e9b2d6, 9e9814d7f549
Create Date: 2026-11-27

"""
from typing import Sequence, Union

revision: str = "d1e5b7a3c920"
down_revision: Union[str, Sequence[str], None] = ("c7a1f4e9b2d6", "9e9814d7f549")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

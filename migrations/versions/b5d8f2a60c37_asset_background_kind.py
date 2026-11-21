"""asset library: background kind for lobby background images

Revision ID: b5d8f2a60c37
Revises: a9e4c7b13d58
Create Date: 2026-11-21 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b5d8f2a60c37"
down_revision: Union[str, Sequence[str], None] = "a9e4c7b13d58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = "kind IN ('rank', 'prop', 'item', 'character', 'currency', 'badge', 'other', 'model')"
NEW = "kind IN ('rank', 'prop', 'item', 'character', 'currency', 'badge', 'other', 'model', 'background')"


def upgrade() -> None:
    with op.batch_alter_table("game_assets") as batch:
        batch.drop_constraint(op.f("ck_game_assets_kind"), type_="check")
        batch.create_check_constraint(op.f("ck_game_assets_kind"), NEW)


def downgrade() -> None:
    op.execute("DELETE FROM game_assets WHERE kind = 'background'")
    with op.batch_alter_table("game_assets") as batch:
        batch.drop_constraint(op.f("ck_game_assets_kind"), type_="check")
        batch.create_check_constraint(op.f("ck_game_assets_kind"), OLD)

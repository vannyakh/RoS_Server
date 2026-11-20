"""asset library: model kind for binary glTF (.glb) 3D models

Revision ID: a3b8e6d24c51
Revises: e8a2c5f17b90
Create Date: 2026-11-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a3b8e6d24c51"
down_revision: Union[str, Sequence[str], None] = "e8a2c5f17b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = "kind IN ('rank', 'prop', 'item', 'character', 'currency', 'badge', 'other')"
NEW = "kind IN ('rank', 'prop', 'item', 'character', 'currency', 'badge', 'other', 'model')"


def upgrade() -> None:
    with op.batch_alter_table("game_assets") as batch:
        batch.drop_constraint(op.f("ck_game_assets_kind"), type_="check")
        batch.create_check_constraint(op.f("ck_game_assets_kind"), NEW)


def downgrade() -> None:
    op.execute("DELETE FROM game_assets WHERE kind = 'model'")
    with op.batch_alter_table("game_assets") as batch:
        batch.drop_constraint(op.f("ck_game_assets_kind"), type_="check")
        batch.create_check_constraint(op.f("ck_game_assets_kind"), OLD)

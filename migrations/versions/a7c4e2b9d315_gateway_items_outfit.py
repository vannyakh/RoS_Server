"""gateway items and outfit (original-client owned appearance and worn lists)

Revision ID: a7c4e2b9d315
Revises: f2b7d4e90a13
Create Date: 2026-11-19 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c4e2b9d315"
down_revision: Union[str, Sequence[str], None] = "f2b7d4e90a13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_identities") as batch:
        batch.add_column(sa.Column("outfit", sa.JSON(), nullable=True))
    op.create_table(
        "gateway_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("prop_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.CheckConstraint("number >= 0", name=op.f("ck_gateway_items_number")),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["gateway_identities.id"],
            name=op.f("fk_gateway_items_identity_id_gateway_identities"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateway_items")),
        sa.UniqueConstraint("identity_id", "prop_id", name="uq_gateway_items_identity_prop"),
    )
    op.create_index(op.f("ix_gateway_items_identity_id"), "gateway_items", ["identity_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_gateway_items_identity_id"), table_name="gateway_items")
    op.drop_table("gateway_items")
    with op.batch_alter_table("gateway_identities") as batch:
        batch.drop_column("outfit")

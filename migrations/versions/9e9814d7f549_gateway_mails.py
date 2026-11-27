"""gateway mails: system mail for original-client players (RO-116)

Revision ID: 9e9814d7f549
Revises: c8f3a5d27e14
Create Date: 2026-11-26 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9e9814d7f549"
down_revision: Union[str, Sequence[str], None] = "c8f3a5d27e14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gateway_mails",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("mail_id", sa.Integer(), nullable=False),
        sa.Column("mail_type", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("content", sa.String(length=2000), nullable=False),
        sa.Column("sender", sa.String(length=32), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("gold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by", sa.String(length=64), nullable=True),
        sa.CheckConstraint("mail_id >= 1", name=op.f("ck_gateway_mails_mail_id")),
        sa.CheckConstraint("mail_type IN (0, 1)", name=op.f("ck_gateway_mails_mail_type")),
        sa.CheckConstraint("gold >= 0", name=op.f("ck_gateway_mails_gold")),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["gateway_identities.id"],
            name=op.f("fk_gateway_mails_identity_id_gateway_identities"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateway_mails")),
        sa.UniqueConstraint("identity_id", "mail_id", name="uq_gateway_mails_identity_mail"),
    )
    op.create_index("ix_gateway_mails_identity_sent", "gateway_mails", ["identity_id", "sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_gateway_mails_identity_sent", table_name="gateway_mails")
    op.drop_table("gateway_mails")

"""support cases, reports, and moderation reasons

Revision ID: d8f1a6c04e21
Revises: c4a8e1b27f03
Create Date: 2026-11-11 23:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8f1a6c04e21"
down_revision: Union[str, Sequence[str], None] = "c4a8e1b27f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("reason", sa.String(length=240), nullable=False, server_default=""))
    op.create_table(
        "support_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assignee_id", sa.String(length=36), nullable=True),
        sa.Column("resolution", sa.String(length=240), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting', 'escalated', 'resolved', 'closed')",
            name="ck_support_cases_status",
        ),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_support_cases_priority"),
        sa.CheckConstraint(
            "category IN ('account_access', 'login', 'progress', 'purchase', 'matchmaking', 'gameplay', 'bug', 'other')",
            name="ck_support_cases_category",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_support_cases_account_id_accounts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assignee_id"], ["operators.id"], name="fk_support_cases_assignee_id_operators", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_support_cases"),
    )
    op.create_index("ix_support_cases_account_id", "support_cases", ["account_id"])
    op.create_index("ix_support_cases_status_created", "support_cases", ["status", "created_at"])
    op.create_table(
        "support_notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.CheckConstraint("visibility IN ('internal', 'reply')", name="ck_support_notes_visibility"),
        sa.ForeignKeyConstraint(["case_id"], ["support_cases.id"], name="fk_support_notes_case_id_support_cases", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_id"], ["operators.id"], name="fk_support_notes_operator_id_operators", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_support_notes"),
    )
    op.create_index("ix_support_notes_case_id", "support_notes", ["case_id"])
    op.create_table(
        "player_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reporter_account_id", sa.String(length=36), nullable=True),
        sa.Column("reported_account_id", sa.String(length=36), nullable=False),
        sa.Column("match_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("assignee_id", sa.String(length=36), nullable=True),
        sa.Column("resolution", sa.String(length=240), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'reviewing', 'dismissed', 'confirmed', 'closed')",
            name="ck_player_reports_status",
        ),
        sa.CheckConstraint(
            "category IN ('account_access', 'login', 'progress', 'purchase', 'matchmaking', 'gameplay', 'bug', 'other')",
            name="ck_player_reports_category",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_account_id"],
            ["accounts.id"],
            name="fk_player_reports_reporter_account_id_accounts",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reported_account_id"],
            ["accounts.id"],
            name="fk_player_reports_reported_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["operators.id"],
            name="fk_player_reports_assignee_id_operators",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_player_reports"),
    )
    op.create_index("ix_player_reports_reported_account_id", "player_reports", ["reported_account_id"])
    op.create_index("ix_player_reports_status_created", "player_reports", ["status", "created_at"])
    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("resulting_status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "action IN ('suspend', 'reactivate', 'ban', 'unban', 'note')",
            name="ck_moderation_actions_action",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_moderation_actions_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["operators.id"],
            name="fk_moderation_actions_operator_id_operators",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_actions"),
    )
    op.create_index("ix_moderation_actions_account_created", "moderation_actions", ["account_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_moderation_actions_account_created", table_name="moderation_actions")
    op.drop_table("moderation_actions")
    op.drop_index("ix_player_reports_status_created", table_name="player_reports")
    op.drop_index("ix_player_reports_reported_account_id", table_name="player_reports")
    op.drop_table("player_reports")
    op.drop_index("ix_support_notes_case_id", table_name="support_notes")
    op.drop_table("support_notes")
    op.drop_index("ix_support_cases_status_created", table_name="support_cases")
    op.drop_index("ix_support_cases_account_id", table_name="support_cases")
    op.drop_table("support_cases")
    op.drop_column("audit_logs", "reason")

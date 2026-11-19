"""Support cases, reports, and moderation records. These are staff records, not player profiles."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin

_CASE_STATUS = "status IN ('open', 'in_progress', 'waiting', 'escalated', 'resolved', 'closed')"
_PRIORITY = "priority IN ('low', 'normal', 'high', 'urgent')"
_CATEGORY = (
    "category IN ('account_access', 'login', 'progress', 'purchase', 'matchmaking', 'gameplay', 'bug', 'other')"
)
_REPORT_STATUS = "status IN ('open', 'reviewing', 'dismissed', 'confirmed', 'closed')"
_ACTION = "action IN ('suspend', 'reactivate', 'ban', 'unban', 'note')"


class SupportCase(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "support_cases"
    __table_args__ = (
        CheckConstraint(_CASE_STATUS, name="ck_support_cases_status"),
        CheckConstraint(_PRIORITY, name="ck_support_cases_priority"),
        CheckConstraint(_CATEGORY, name="ck_support_cases_category"),
        Index("ix_support_cases_status_created", "status", "created_at"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)
    resolution: Mapped[str] = mapped_column(String(240), default="", nullable=False)


class SupportNote(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "support_notes"
    __table_args__ = (CheckConstraint("visibility IN ('internal', 'reply')", name="ck_support_notes_visibility"),)

    case_id: Mapped[str] = mapped_column(ForeignKey("support_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), default="internal", nullable=False)


class PlayerReport(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "player_reports"
    __table_args__ = (
        CheckConstraint(_REPORT_STATUS, name="ck_player_reports_status"),
        CheckConstraint(_CATEGORY, name="ck_player_reports_category"),
        Index("ix_player_reports_status_created", "status", "created_at"),
    )

    reporter_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)
    resolution: Mapped[str] = mapped_column(String(240), default="", nullable=False)


class ModerationAction(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "moderation_actions"
    __table_args__ = (
        CheckConstraint(_ACTION, name="ck_moderation_actions_action"),
        Index("ix_moderation_actions_account_created", "account_id", "created_at"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    resulting_status: Mapped[str] = mapped_column(String(16), nullable=False)

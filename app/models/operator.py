"""Operators are staff accounts. They are not player profiles and cannot sign in as a player."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin


class Operator(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "operators"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="status"),
        Index("ix_operators_status", "status"),
    )

    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["OperatorSession"]] = relationship(
        back_populates="operator",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    roles: Mapped[list["OperatorRole"]] = relationship(
        back_populates="operator",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )


class OperatorSession(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "operator_sessions"
    __table_args__ = (Index("ix_operator_sessions_operator_expires", "operator_id", "expires_at"),)

    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    operator: Mapped[Operator] = relationship(back_populates="sessions", lazy="raise")


class Permission(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)


class Role(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )


class RolePermission(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),)

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)

    role: Mapped[Role] = relationship(back_populates="permissions", lazy="raise")
    permission: Mapped[Permission] = relationship(lazy="raise")


class OperatorRole(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "operator_roles"
    __table_args__ = (UniqueConstraint("operator_id", "role_id", name="uq_operator_roles_operator_role"),)

    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    operator: Mapped[Operator] = relationship(back_populates="roles", lazy="raise")
    role: Mapped[Role] = relationship(lazy="raise")


class AuditLog(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created", "created_at"),)

    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    reason: Mapped[str] = mapped_column(String(240), default="", nullable=False)

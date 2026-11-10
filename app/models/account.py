"""Login accounts. A profile lives on Player; this table never leaves the database layer as a password hash."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin

_ACCOUNT_STATUSES = ("active", "suspended", "closed")


class Account(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'closed')", name="status"),
        Index("ix_accounts_status", "status"),
    )

    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["AccountSession"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    devices: Mapped[list["AccountDevice"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    login_history: Mapped[list["LoginHistory"]] = relationship(
        back_populates="account",
        lazy="raise",
        passive_deletes=True,
    )
    player: Mapped["Player | None"] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="raise",
        uselist=False,
        passive_deletes=True,
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class AccountSession(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "account_sessions"
    __table_args__ = (Index("ix_account_sessions_account_expires", "account_id", "expires_at"),)

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account] = relationship(back_populates="sessions", lazy="raise")


class AccountDevice(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "account_devices"
    __table_args__ = (
        Index("uq_account_devices_account_device", "account_id", "device_identifier", unique=True),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    device_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[Account] = relationship(back_populates="devices", lazy="raise")


class LoginHistory(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "login_history"
    __table_args__ = (
        CheckConstraint("login_status IN ('success', 'failure')", name="login_status"),
        Index("ix_login_history_account_created", "account_id", "created_at"),
    )

    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    login_status: Mapped[str] = mapped_column(String(16), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    account: Mapped[Account | None] = relationship(back_populates="login_history", lazy="raise")

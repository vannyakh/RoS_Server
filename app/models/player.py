"""One profile per account. Match totals live on PlayerStatistics, not on the login row."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin


class Player(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("level >= 1", name="level"),
        CheckConstraint("experience >= 0", name="experience"),
        CheckConstraint("status IN ('active', 'inactive')", name="status"),
        UniqueConstraint("account_id", name="uq_players_account_id"),
        Index("ix_players_status", "status"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    nickname: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    avatar_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    level: Mapped[int] = mapped_column(default=1, nullable=False)
    experience: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    account: Mapped["Account"] = relationship(back_populates="player", lazy="raise")
    statistics: Mapped["PlayerStatistics | None"] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="raise",
        uselist=False,
        passive_deletes=True,
    )
    progression: Mapped[list["PlayerProgression"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    inventory: Mapped["PlayerInventory | None"] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="raise",
        uselist=False,
        passive_deletes=True,
    )
    currencies: Mapped[list["PlayerCurrency"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )


class PlayerStatistics(IdMixin, UpdatedAtMixin, Base):
    __tablename__ = "player_statistics"
    __table_args__ = (
        CheckConstraint("total_matches >= 0", name="total_matches"),
        CheckConstraint("total_wins >= 0", name="total_wins"),
        CheckConstraint("total_kills >= 0", name="total_kills"),
        CheckConstraint("total_deaths >= 0", name="total_deaths"),
        CheckConstraint("total_playtime_seconds >= 0", name="total_playtime"),
        UniqueConstraint("player_id", name="uq_player_statistics_player_id"),
    )

    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    total_matches: Mapped[int] = mapped_column(default=0, nullable=False)
    total_wins: Mapped[int] = mapped_column(default=0, nullable=False)
    total_kills: Mapped[int] = mapped_column(default=0, nullable=False)
    total_deaths: Mapped[int] = mapped_column(default=0, nullable=False)
    total_playtime_seconds: Mapped[int] = mapped_column(default=0, nullable=False)

    player: Mapped[Player] = relationship(back_populates="statistics", lazy="raise")


class PlayerProgression(IdMixin, UpdatedAtMixin, Base):
    __tablename__ = "player_progression"
    __table_args__ = (
        CheckConstraint("progression_level >= 1", name="progression_level"),
        CheckConstraint("progression_experience >= 0", name="progression_experience"),
        UniqueConstraint("player_id", "progression_type", name="uq_player_progression_type"),
    )

    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    progression_type: Mapped[str] = mapped_column(String(32), nullable=False)
    progression_level: Mapped[int] = mapped_column(default=1, nullable=False)
    progression_experience: Mapped[int] = mapped_column(default=0, nullable=False)

    player: Mapped[Player] = relationship(back_populates="progression", lazy="raise")

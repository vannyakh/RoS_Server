"""Lobby and team membership. High-frequency movement is not stored here."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin


class Lobby(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "lobbies"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'starting', 'closed')", name="status"),
        CheckConstraint("max_players > 0", name="max_players"),
        CheckConstraint("current_players >= 0", name="current_players"),
    )

    code: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    max_players: Mapped[int] = mapped_column(default=4, nullable=False)
    current_players: Mapped[int] = mapped_column(default=0, nullable=False)
    game_mode_id: Mapped[str | None] = mapped_column(ForeignKey("game_modes.id", ondelete="SET NULL"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    members: Mapped[list["LobbyMember"]] = relationship(
        back_populates="lobby",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    teams: Mapped[list["Team"]] = relationship(
        back_populates="lobby",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )


class LobbyMember(IdMixin, Base):
    __tablename__ = "lobby_members"
    __table_args__ = (UniqueConstraint("lobby_id", "player_id", name="uq_lobby_members_player"),)

    lobby_id: Mapped[str] = mapped_column(ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready: Mapped[bool] = mapped_column(default=False, nullable=False)

    lobby: Mapped[Lobby] = relationship(back_populates="members", lazy="raise")
    player: Mapped["Player"] = relationship(lazy="raise")


class Team(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("lobby_id", "code", name="uq_teams_lobby_code"),)

    lobby_id: Mapped[str] = mapped_column(ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)

    lobby: Mapped[Lobby] = relationship(back_populates="teams", lazy="raise")
    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )


class TeamMember(IdMixin, Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "player_id", name="uq_team_members_player"),
        UniqueConstraint("lobby_id", "player_id", name="uq_team_members_lobby_player"),
    )

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    lobby_id: Mapped[str] = mapped_column(ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    team: Mapped[Team] = relationship(back_populates="members", lazy="raise")
    player: Mapped["Player"] = relationship(lazy="raise")

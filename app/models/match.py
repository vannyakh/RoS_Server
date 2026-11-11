"""Durable match records. Positions and aim stay in memory; only the finished result is stored."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON

_MATCH_STATUSES = "status IN ('scheduled', 'lobby', 'running', 'completed', 'cancelled')"


class Match(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(_MATCH_STATUSES, name="status"),
        CheckConstraint("max_players > 0", name="max_players"),
        CheckConstraint("current_players >= 0", name="current_players"),
        Index("ix_matches_status_created_at", "status", "created_at"),
    )

    match_code: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    game_mode_id: Mapped[str | None] = mapped_column(ForeignKey("game_modes.id", ondelete="RESTRICT"), nullable=True)
    map_id: Mapped[str | None] = mapped_column(ForeignKey("map_definitions.id", ondelete="RESTRICT"), nullable=True)
    map_version_id: Mapped[str | None] = mapped_column(ForeignKey("map_versions.id", ondelete="RESTRICT"), nullable=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="scheduled", nullable=False)
    max_players: Mapped[int] = mapped_column(default=100, nullable=False)
    current_players: Mapped[int] = mapped_column(default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    game_mode: Mapped["GameMode | None"] = relationship(lazy="raise")
    map_definition: Mapped["MapDefinition | None"] = relationship(lazy="raise")
    map_version: Mapped["MapVersion | None"] = relationship(lazy="raise")
    participants: Mapped[list["MatchParticipant"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    results: Mapped[list["MatchResult"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    statistics: Mapped["MatchStatistics | None"] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        lazy="raise",
        uselist=False,
        passive_deletes=True,
    )


class MatchParticipant(IdMixin, Base):
    __tablename__ = "match_participants"
    __table_args__ = (
        CheckConstraint("kills >= 0", name="kills"),
        CheckConstraint("deaths >= 0", name="deaths"),
        CheckConstraint("survival_seconds >= 0", name="survival_seconds"),
        UniqueConstraint("match_id", "player_id", name="uq_match_participants_player"),
        Index("ix_match_participants_player_id", "player_id"),
    )

    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    placement: Mapped[int | None] = mapped_column(nullable=True)
    kills: Mapped[int] = mapped_column(default=0, nullable=False)
    deaths: Mapped[int] = mapped_column(default=0, nullable=False)
    survival_seconds: Mapped[int] = mapped_column(default=0, nullable=False)

    match: Mapped[Match] = relationship(back_populates="participants", lazy="raise")
    player: Mapped["Player"] = relationship(lazy="raise")


class MatchResult(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "match_results"
    __table_args__ = (
        CheckConstraint("kills >= 0", name="kills"),
        CheckConstraint("score >= 0", name="score"),
        UniqueConstraint("match_id", "player_id", name="uq_match_results_player"),
    )

    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    placement: Mapped[int] = mapped_column(nullable=False)
    kills: Mapped[int] = mapped_column(default=0, nullable=False)
    score: Mapped[int] = mapped_column(default=0, nullable=False)
    rewards: Mapped[dict] = mapped_column(PortableJSON, default=dict, nullable=False)

    match: Mapped[Match] = relationship(back_populates="results", lazy="raise")
    player: Mapped["Player"] = relationship(lazy="raise")


class MatchStatistics(IdMixin, Base):
    __tablename__ = "match_statistics"
    __table_args__ = (UniqueConstraint("match_id", name="uq_match_statistics_match_id"),)

    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    participant_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_kills: Mapped[int] = mapped_column(default=0, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(default=0, nullable=False)
    summary: Mapped[dict] = mapped_column(PortableJSON, default=dict, nullable=False)

    match: Mapped[Match] = relationship(back_populates="statistics", lazy="raise")

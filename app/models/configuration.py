"""Versioned server settings. Routes read these rows instead of embedding rules."""

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON, UpdatedAtMixin


class ServerConfiguration(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "server_configurations"
    __table_args__ = (UniqueConstraint("config_key", name="uq_server_configurations_key"),)

    config_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(PortableJSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GameConfiguration(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "game_configurations"
    __table_args__ = (UniqueConstraint("config_key", name="uq_game_configurations_key"),)

    config_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(PortableJSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeatureConfiguration(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "feature_configurations"
    __table_args__ = (UniqueConstraint("code", name="uq_feature_configurations_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    value: Mapped[dict] = mapped_column(PortableJSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

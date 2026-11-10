"""Reference definitions authored for this server. These rows are not official game assets."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON, UpdatedAtMixin


class _Definition(IdMixin, CreatedAtMixin, UpdatedAtMixin):
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    details: Mapped[dict] = mapped_column("metadata", PortableJSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class GameMode(_Definition, Base):
    __tablename__ = "game_modes"

    team_size: Mapped[int] = mapped_column(default=1, nullable=False)
    min_players: Mapped[int] = mapped_column(default=1, nullable=False)
    max_players: Mapped[int] = mapped_column(default=100, nullable=False)


class MapDefinition(_Definition, Base):
    __tablename__ = "map_definitions"

    width: Mapped[int] = mapped_column(default=200, nullable=False)
    height: Mapped[int] = mapped_column(default=200, nullable=False)


class ItemDefinition(_Definition, Base):
    __tablename__ = "item_definitions"

    category: Mapped[str] = mapped_column(String(32), default="misc", nullable=False)
    max_stack: Mapped[int] = mapped_column(default=1, nullable=False)


class WeaponDefinition(_Definition, Base):
    __tablename__ = "weapon_definitions"

    item_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("item_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    damage: Mapped[int] = mapped_column(default=1, nullable=False)
    range_units: Mapped[int] = mapped_column(default=1, nullable=False)
    magazine_size: Mapped[int] = mapped_column(default=1, nullable=False)

    item_definition: Mapped[ItemDefinition | None] = relationship(lazy="raise")


class EquipmentDefinition(_Definition, Base):
    __tablename__ = "equipment_definitions"

    slot: Mapped[str] = mapped_column(String(32), default="misc", nullable=False)


class VehicleDefinition(_Definition, Base):
    __tablename__ = "vehicle_definitions"

    seats: Mapped[int] = mapped_column(default=1, nullable=False)


class RankDefinition(_Definition, Base):
    __tablename__ = "rank_definitions"

    threshold_score: Mapped[int] = mapped_column(default=0, nullable=False)


class AchievementDefinition(_Definition, Base):
    __tablename__ = "achievement_definitions"

    points: Mapped[int] = mapped_column(default=0, nullable=False)

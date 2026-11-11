"""Versioned map packages. Binary files stay in storage; these rows are metadata."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON

_VERSION_STATUSES = "status IN ('draft', 'published', 'retired')"


class MapVersion(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "map_versions"
    __table_args__ = (
        CheckConstraint(_VERSION_STATUSES, name="status"),
        CheckConstraint("schema_version >= 1", name="schema_version"),
        CheckConstraint("size_x > 0 AND size_y > 0 AND size_z > 0", name="size"),
        UniqueConstraint("map_id", "version", name="uq_map_versions_map_version"),
        Index("ix_map_versions_map_id_status", "map_id", "status"),
    )

    map_id: Mapped[str] = mapped_column(ForeignKey("map_definitions.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_profile: Mapped[str] = mapped_column(String(32), default="portable_gltf", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    origin_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    origin_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    origin_z: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    size_x: Mapped[float] = mapped_column(Float, nullable=False)
    size_y: Mapped[float] = mapped_column(Float, nullable=False)
    size_z: Mapped[float] = mapped_column(Float, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publisher_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    map_definition: Mapped["MapDefinition"] = relationship(back_populates="versions", lazy="raise")
    assets: Mapped[list["MapAsset"]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="raise", passive_deletes=True)
    regions: Mapped[list["MapRegion"]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="raise", passive_deletes=True)
    objects: Mapped[list["MapObject"]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="raise", passive_deletes=True)
    spawn_points: Mapped[list["MapSpawnPoint"]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="raise", passive_deletes=True)
    points_of_interest: Mapped[list["MapPointOfInterest"]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="raise", passive_deletes=True)
    publication: Mapped["MapPublication | None"] = relationship(back_populates="version", lazy="raise", uselist=False)


class MapAsset(IdMixin, Base):
    __tablename__ = "map_assets"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes"),
        UniqueConstraint("map_version_id", "relative_path", name="uq_map_assets_path"),
        Index("ix_map_assets_map_version_id", "map_version_id"),
    )

    map_version_id: Mapped[str] = mapped_column(ForeignKey("map_versions.id", ondelete="CASCADE"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(240), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column("metadata", PortableJSON, default=dict, nullable=False)

    version: Mapped[MapVersion] = relationship(back_populates="assets", lazy="raise")


class MapRegion(IdMixin, Base):
    __tablename__ = "map_regions"
    __table_args__ = (UniqueConstraint("map_version_id", "code", name="uq_map_regions_code"),)

    map_version_id: Mapped[str] = mapped_column(ForeignKey("map_versions.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    min_x: Mapped[float] = mapped_column(Float, nullable=False)
    min_y: Mapped[float] = mapped_column(Float, nullable=False)
    min_z: Mapped[float] = mapped_column(Float, nullable=False)
    max_x: Mapped[float] = mapped_column(Float, nullable=False)
    max_y: Mapped[float] = mapped_column(Float, nullable=False)
    max_z: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict] = mapped_column("metadata", PortableJSON, default=dict, nullable=False)

    version: Mapped[MapVersion] = relationship(back_populates="regions", lazy="raise")


class MapObject(IdMixin, Base):
    __tablename__ = "map_objects"
    __table_args__ = (UniqueConstraint("map_version_id", "object_code", name="uq_map_objects_code"),)

    map_version_id: Mapped[str] = mapped_column(ForeignKey("map_versions.id", ondelete="CASCADE"), nullable=False)
    object_code: Mapped[str] = mapped_column(String(64), nullable=False)
    definition_code: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    position_z: Mapped[float] = mapped_column(Float, nullable=False)
    rotation_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rotation_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rotation_z: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scale_x: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    scale_y: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    scale_z: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    collision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    navigation_obstacle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interactive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details: Mapped[dict] = mapped_column("metadata", PortableJSON, default=dict, nullable=False)

    version: Mapped[MapVersion] = relationship(back_populates="objects", lazy="raise")


class MapSpawnPoint(IdMixin, Base):
    __tablename__ = "map_spawn_points"
    __table_args__ = (UniqueConstraint("map_version_id", "spawn_code", name="uq_map_spawn_points_code"),)

    map_version_id: Mapped[str] = mapped_column(ForeignKey("map_versions.id", ondelete="CASCADE"), nullable=False)
    spawn_code: Mapped[str] = mapped_column(String(64), nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    position_z: Mapped[float] = mapped_column(Float, nullable=False)
    rotation_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spawn_group: Mapped[str] = mapped_column(String(32), default="default", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    version: Mapped[MapVersion] = relationship(back_populates="spawn_points", lazy="raise")


class MapPointOfInterest(IdMixin, Base):
    __tablename__ = "map_points_of_interest"
    __table_args__ = (UniqueConstraint("map_version_id", "poi_code", name="uq_map_points_of_interest_code"),)

    map_version_id: Mapped[str] = mapped_column(ForeignKey("map_versions.id", ondelete="CASCADE"), nullable=False)
    poi_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    position_z: Mapped[float] = mapped_column(Float, nullable=False)
    icon: Mapped[str] = mapped_column(String(32), default="marker", nullable=False)

    version: Mapped[MapVersion] = relationship(back_populates="points_of_interest", lazy="raise")


class MapPublication(IdMixin, Base):
    __tablename__ = "map_publications"
    __table_args__ = (UniqueConstraint("map_version_id", name="uq_map_publications_version"),)

    map_version_id: Mapped[str] = mapped_column(ForeignKey("map_versions.id", ondelete="RESTRICT"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_by: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)

    version: Mapped[MapVersion] = relationship(back_populates="publication", lazy="raise")

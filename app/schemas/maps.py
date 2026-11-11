"""Map catalog and administration schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MapCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    width: int = Field(ge=1, le=100000)
    height: int = Field(ge=1, le=100000)


class MapUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    width: int | None = Field(default=None, ge=1, le=100000)
    height: int | None = Field(default=None, ge=1, le=100000)


class MapRegionCreate(BaseModel):
    code: str
    name: str = Field(min_length=1, max_length=80)
    minimum: list[float]
    maximum: list[float]


class MapObjectCreate(BaseModel):
    object_code: str
    definition_code: str
    category: str
    position: list[float]
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])
    collision: bool = False
    navigation_obstacle: bool = False
    interactive: bool = False


class MapSpawnCreate(BaseModel):
    spawn_code: str
    position: list[float]
    rotation_y: float = 0.0
    spawn_group: str = Field(default="default", min_length=1, max_length=32)
    enabled: bool = True


class MapPoiCreate(BaseModel):
    poi_code: str
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    position: list[float]
    icon: str = Field(default="marker", min_length=1, max_length=32)


class MapVersionCreate(BaseModel):
    version: str
    schema_version: int = 1
    engine_profile: str = Field(default="portable_gltf", min_length=1, max_length=32)
    origin: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    size: list[float]
    regions: list[MapRegionCreate] = Field(default_factory=list)
    objects: list[MapObjectCreate] = Field(default_factory=list)
    spawn_points: list[MapSpawnCreate] = Field(default_factory=list)
    points_of_interest: list[MapPoiCreate] = Field(default_factory=list)


class MapPublish(BaseModel):
    version_id: str


class MapPin(BaseModel):
    version_id: str
    match_id: str


class MapSummary(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    current_version: str
    manifest_hash: str
    download_size_bytes: int


class MapVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: str
    schema_version: int
    engine_profile: str
    status: str
    manifest_hash: str | None
    published_at: datetime | None


class MapDetail(MapSummary):
    width: int
    height: int
    coordinate_system: str
    origin: list[float]
    size: list[float]


class MapAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_type: str
    relative_path: str
    mime_type: str
    size_bytes: int
    sha256: str


class ManifestFile(BaseModel):
    asset_id: str
    path: str
    sha256: str
    size_bytes: int
    type: str


class ManifestResponse(BaseModel):
    coordinate_system: str
    engine_profile: str
    files: list[ManifestFile]
    map_id: str
    schema_version: int
    slug: str
    version: str
    manifest_hash: str

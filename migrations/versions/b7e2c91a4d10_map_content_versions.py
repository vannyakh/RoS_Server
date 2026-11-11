"""map content versions

Revision ID: b7e2c91a4d10
Revises: 93510e8bf194
Create Date: 2026-11-11 08:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e2c91a4d10"
down_revision: Union[str, Sequence[str], None] = "93510e8bf194"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "map_versions",
        sa.Column("map_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("engine_profile", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("origin_x", sa.Float(), nullable=False),
        sa.Column("origin_y", sa.Float(), nullable=False),
        sa.Column("origin_z", sa.Float(), nullable=False),
        sa.Column("size_x", sa.Float(), nullable=False),
        sa.Column("size_y", sa.Float(), nullable=False),
        sa.Column("size_z", sa.Float(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publisher_account_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_versions"),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_map_versions_status"),
        sa.CheckConstraint("schema_version >= 1", name="ck_map_versions_schema_version"),
        sa.CheckConstraint("size_x > 0 AND size_y > 0 AND size_z > 0", name="ck_map_versions_size"),
        sa.ForeignKeyConstraint(["map_id"], ["map_definitions.id"], name="fk_map_versions_map_id_map_definitions", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publisher_account_id"], ["accounts.id"], name="fk_map_versions_publisher_account_id_accounts", ondelete="SET NULL"),
        sa.UniqueConstraint("map_id", "version", name="uq_map_versions_map_version"),
    )
    op.create_index("ix_map_versions_map_id_status", "map_versions", ["map_id", "status"])
    op.create_table(
        "map_assets",
        sa.Column("map_version_id", sa.String(length=36), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("relative_path", sa.String(length=200), nullable=False),
        sa.Column("storage_key", sa.String(length=240), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata", JSON, nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_assets"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_map_assets_size_bytes"),
        sa.ForeignKeyConstraint(["map_version_id"], ["map_versions.id"], name="fk_map_assets_map_version_id_map_versions", ondelete="CASCADE"),
        sa.UniqueConstraint("map_version_id", "relative_path", name="uq_map_assets_path"),
    )
    op.create_index("ix_map_assets_map_version_id", "map_assets", ["map_version_id"])
    op.create_table(
        "map_regions",
        sa.Column("map_version_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("min_x", sa.Float(), nullable=False),
        sa.Column("min_y", sa.Float(), nullable=False),
        sa.Column("min_z", sa.Float(), nullable=False),
        sa.Column("max_x", sa.Float(), nullable=False),
        sa.Column("max_y", sa.Float(), nullable=False),
        sa.Column("max_z", sa.Float(), nullable=False),
        sa.Column("metadata", JSON, nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_regions"),
        sa.ForeignKeyConstraint(["map_version_id"], ["map_versions.id"], name="fk_map_regions_map_version_id_map_versions", ondelete="CASCADE"),
        sa.UniqueConstraint("map_version_id", "code", name="uq_map_regions_code"),
    )
    op.create_table(
        "map_objects",
        sa.Column("map_version_id", sa.String(length=36), nullable=False),
        sa.Column("object_code", sa.String(length=64), nullable=False),
        sa.Column("definition_code", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("position_x", sa.Float(), nullable=False),
        sa.Column("position_y", sa.Float(), nullable=False),
        sa.Column("position_z", sa.Float(), nullable=False),
        sa.Column("rotation_x", sa.Float(), nullable=False),
        sa.Column("rotation_y", sa.Float(), nullable=False),
        sa.Column("rotation_z", sa.Float(), nullable=False),
        sa.Column("scale_x", sa.Float(), nullable=False),
        sa.Column("scale_y", sa.Float(), nullable=False),
        sa.Column("scale_z", sa.Float(), nullable=False),
        sa.Column("collision", sa.Boolean(), nullable=False),
        sa.Column("navigation_obstacle", sa.Boolean(), nullable=False),
        sa.Column("interactive", sa.Boolean(), nullable=False),
        sa.Column("metadata", JSON, nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_objects"),
        sa.ForeignKeyConstraint(["map_version_id"], ["map_versions.id"], name="fk_map_objects_map_version_id_map_versions", ondelete="CASCADE"),
        sa.UniqueConstraint("map_version_id", "object_code", name="uq_map_objects_code"),
    )
    op.create_table(
        "map_spawn_points",
        sa.Column("map_version_id", sa.String(length=36), nullable=False),
        sa.Column("spawn_code", sa.String(length=64), nullable=False),
        sa.Column("position_x", sa.Float(), nullable=False),
        sa.Column("position_y", sa.Float(), nullable=False),
        sa.Column("position_z", sa.Float(), nullable=False),
        sa.Column("rotation_y", sa.Float(), nullable=False),
        sa.Column("spawn_group", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_spawn_points"),
        sa.ForeignKeyConstraint(["map_version_id"], ["map_versions.id"], name="fk_map_spawn_points_map_version_id_map_versions", ondelete="CASCADE"),
        sa.UniqueConstraint("map_version_id", "spawn_code", name="uq_map_spawn_points_code"),
    )
    op.create_table(
        "map_points_of_interest",
        sa.Column("map_version_id", sa.String(length=36), nullable=False),
        sa.Column("poi_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position_x", sa.Float(), nullable=False),
        sa.Column("position_y", sa.Float(), nullable=False),
        sa.Column("position_z", sa.Float(), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_points_of_interest"),
        sa.ForeignKeyConstraint(["map_version_id"], ["map_versions.id"], name="fk_map_points_of_interest_map_version_id_map_versions", ondelete="CASCADE"),
        sa.UniqueConstraint("map_version_id", "poi_code", name="uq_map_points_of_interest_code"),
    )
    op.create_table(
        "map_publications",
        sa.Column("map_version_id", sa.String(length=36), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_map_publications"),
        sa.ForeignKeyConstraint(["map_version_id"], ["map_versions.id"], name="fk_map_publications_map_version_id_map_versions", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["accounts.id"], name="fk_map_publications_published_by_accounts", ondelete="RESTRICT"),
        sa.UniqueConstraint("map_version_id", name="uq_map_publications_version"),
    )
    with op.batch_alter_table("matches") as batch:
        batch.add_column(sa.Column("map_version_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("manifest_hash", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_matches_map_version_id_map_versions",
            "map_versions",
            ["map_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("matches") as batch:
        batch.drop_constraint("fk_matches_map_version_id_map_versions", type_="foreignkey")
        batch.drop_column("manifest_hash")
        batch.drop_column("map_version_id")
    op.drop_table("map_publications")
    op.drop_table("map_points_of_interest")
    op.drop_table("map_spawn_points")
    op.drop_table("map_objects")
    op.drop_table("map_regions")
    op.drop_index("ix_map_assets_map_version_id", table_name="map_assets")
    op.drop_table("map_assets")
    op.drop_index("ix_map_versions_map_id_status", table_name="map_versions")
    op.drop_table("map_versions")

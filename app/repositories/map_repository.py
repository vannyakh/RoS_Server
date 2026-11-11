"""Map catalog queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game_data import MapDefinition
from app.models.map_content import MapAsset, MapVersion
from app.models.match import Match


class MapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, row: MapDefinition) -> MapDefinition:
        self.session.add(row)
        await self.session.flush()
        return row

    async def definition(self, map_id: str) -> MapDefinition | None:
        return await self.session.get(MapDefinition, map_id)

    async def by_code(self, code: str) -> MapDefinition | None:
        return await self.session.scalar(select(MapDefinition).where(MapDefinition.code == code))

    async def published_page(self, limit: int, offset: int) -> tuple[list[MapDefinition], int]:
        published_ids = select(MapVersion.map_id).where(MapVersion.status == "published").distinct()
        total = await self.session.scalar(select(func.count()).select_from(published_ids.subquery()))
        rows = (
            await self.session.scalars(
                select(MapDefinition)
                .where(MapDefinition.id.in_(published_ids))
                .order_by(MapDefinition.name)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return list(rows), int(total or 0)

    async def add_version(self, row: MapVersion) -> MapVersion:
        self.session.add(row)
        await self.session.flush()
        return row

    async def version(self, version_id: str) -> MapVersion | None:
        return await self.session.scalar(
            select(MapVersion)
            .where(MapVersion.id == version_id)
            .options(
                selectinload(MapVersion.assets),
                selectinload(MapVersion.regions),
                selectinload(MapVersion.objects),
                selectinload(MapVersion.spawn_points),
                selectinload(MapVersion.points_of_interest),
            )
        )

    async def versions_for(self, map_id: str, *, published_only: bool) -> list[MapVersion]:
        query = select(MapVersion).where(MapVersion.map_id == map_id).order_by(MapVersion.created_at)
        if published_only:
            query = query.where(MapVersion.status == "published")
        return list((await self.session.scalars(query)).all())

    async def latest_published(self, map_id: str) -> MapVersion | None:
        return await self.session.scalar(
            select(MapVersion)
            .where(MapVersion.map_id == map_id, MapVersion.status == "published")
            .order_by(MapVersion.published_at.desc())
        )

    async def asset(self, asset_id: str) -> MapAsset | None:
        return await self.session.get(MapAsset, asset_id)

    async def match(self, match_id: str) -> Match | None:
        return await self.session.get(Match, match_id)

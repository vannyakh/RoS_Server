"""Reference item catalog."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_db
from app.schemas.common import Page
from app.schemas.game_data import ItemDefinitionResponse
from app.services.game_data_service import GameDataService

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("", response_model=Page[ItemDefinitionResponse])
async def items(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Page[ItemDefinitionResponse]:
    return await GameDataService(db).list_items(limit, offset)

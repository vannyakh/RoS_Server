"""Stored match lifecycle. Live match snapshots stay on /matches."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player
from app.infrastructure.database import get_db
from app.models.player import Player
from app.schemas.match import MatchFinalize, MatchRecordCreate, MatchRecordResponse, MatchTransition
from app.services.match_service import MatchService

router = APIRouter(prefix="/match-records", tags=["Match records"])


@router.post("", response_model=MatchRecordResponse, status_code=201)
async def create_match_record(
    body: MatchRecordCreate,
    _player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> MatchRecordResponse:
    match = await MatchService(db).create(body.match_code, body.max_players)
    return MatchRecordResponse.model_validate(match, from_attributes=True)


@router.post("/{match_id}/participants", status_code=204)
async def join_match_record(
    match_id: str,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> None:
    await MatchService(db).add_participant(match_id, player.id)


@router.post("/{match_id}/transition", response_model=MatchRecordResponse)
async def transition_match_record(
    match_id: str,
    body: MatchTransition,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> MatchRecordResponse:
    match = await MatchService(db).transition(match_id, body.status, player.id)
    return MatchRecordResponse.model_validate(match, from_attributes=True)


@router.post("/{match_id}/results", response_model=MatchRecordResponse)
async def finalize_match_record(
    match_id: str,
    body: MatchFinalize,
    player: Player = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> MatchRecordResponse:
    results = [row.model_dump() for row in body.results]
    match = await MatchService(db).finalize(match_id, results, player.id)
    return MatchRecordResponse.model_validate(match, from_attributes=True)

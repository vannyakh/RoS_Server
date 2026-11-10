"""Match list and one match snapshot."""

from fastapi import APIRouter, HTTPException

from app.services.matchmaking_service import get_match, list_matches

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("")
async def matches() -> dict:
    return await list_matches()


@router.get("/{match_id}")
async def match_detail(match_id: str) -> dict:
    match = await get_match(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match

"""Active matches from the in-memory matchmaker."""

from app.game.engine import game_engine


async def list_matches() -> dict:
    return await game_engine.list_matches()


async def get_match(match_id: str) -> dict | None:
    return await game_engine.match_status(match_id)

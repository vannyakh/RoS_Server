"""Development game modes. These codes belong to this server, not to an official title."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.seeds._upsert import upsert_code
from app.models.game_data import GameMode

MODES = (
    {"code": "SOLO", "name": "Solo", "description": "Development free-for-all.", "team_size": 1, "min_players": 1, "max_players": 100},
    {"code": "DUO", "name": "Duo", "description": "Development pairs.", "team_size": 2, "min_players": 2, "max_players": 100},
    {"code": "SQUAD", "name": "Squad", "description": "Development groups of four.", "team_size": 4, "min_players": 4, "max_players": 100},
)


async def seed_game_modes(session: AsyncSession) -> None:
    for mode in MODES:
        values = dict(mode)
        code = values.pop("code")
        await upsert_code(session, GameMode, code, details={"fixture": True}, **values)

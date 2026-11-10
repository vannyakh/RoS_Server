"""Durable writes stay outside the game tick. Only finished match totals are stored."""

import logging

from sqlalchemy import select

from app.infrastructure.database import SessionLocal
from app.models.player import Player, PlayerStatistics
from tools.function_tracker import function_tracker

logger = logging.getLogger(__name__)


class PersistenceService:
    async def save_player_progress(self, player_id: str, progress: dict) -> None:
        try:
            with function_tracker.track(
                function_id="match.persist",
                feature="results",
                function_name="save_player_progress",
                player_id=player_id,
            ) as execution:
                execution.mark("DATABASE_OPERATION")
                async with SessionLocal() as session:
                    statistics = await session.scalar(
                        select(PlayerStatistics)
                        .join(Player, Player.id == PlayerStatistics.player_id)
                        .where(Player.account_id == player_id)
                    )
                    if statistics is None:
                        statistics = await session.scalar(
                            select(PlayerStatistics).where(PlayerStatistics.player_id == player_id)
                        )
                    if statistics is None:
                        return
                    statistics.total_kills += int(progress.get("kills") or 0)
                    statistics.total_matches += 1
                    if progress.get("win"):
                        statistics.total_wins += 1
                    await session.commit()
        except Exception:
            logger.exception("Could not save match progress for %s", player_id)


persistence_service = PersistenceService()

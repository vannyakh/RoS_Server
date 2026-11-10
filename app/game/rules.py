"""Tunable match rules. The tick reads these and does not touch the database."""

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class MatchRules:
    map_size: float = 200.0
    speed: float = 5.0
    queue_wait: float = 2.0
    bot_fill: int = 7
    max_players: int = 100
    countdown: float = 3.0
    drop_time: float = 8.0
    phase_duration: float = 25.0
    result_time: float = 8.0
    zone_radii: tuple[float, ...] = (110.0, 70.0, 40.0, 20.0, 8.0)
    zone_dps: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)
    pickup_radius: float = 2.5
    hit_radius: float = 1.25
    loot_count: int = 36


def default_rules() -> MatchRules:
    return MatchRules(
        max_players=settings.max_players_per_match,
        bot_fill=settings.bot_fill,
        queue_wait=settings.queue_wait_seconds,
    )

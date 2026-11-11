"""Point blockers for the tick. A player is a point, and a step checks the destination."""

from app.game.state import Blocker


def slide(
    x: float,
    y: float,
    next_x: float,
    next_y: float,
    blockers: list[Blocker],
) -> tuple[float, float]:
    if not blockers or not _inside(next_x, next_y, blockers):
        return next_x, next_y
    if not _inside(next_x, y, blockers):
        return next_x, y
    if not _inside(x, next_y, blockers):
        return x, next_y
    return x, y


def _inside(x: float, y: float, blockers: list[Blocker]) -> bool:
    return any(
        blocker.minimum_x <= x <= blocker.maximum_x and blocker.minimum_y <= y <= blocker.maximum_y
        for blocker in blockers
    )

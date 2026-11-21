"""Rank tier names for the rank logo assets (asset kind "rank", key = tier name).

Independent design: the score step for each tier is this project's choice. The original client
turns a ranked score into its own tier badge, and those thresholds are Unknown.
"""

RANK_TIERS: tuple[tuple[int, str], ...] = (
    (0, "bronze"),
    (1000, "silver"),
    (2000, "gold"),
    (3000, "platinum"),
    (4000, "diamond"),
    (5000, "master"),
    (6000, "king"),
)


def rank_tier(score: int) -> str:
    tier = RANK_TIERS[0][1]
    for floor, name in RANK_TIERS:
        if score >= floor:
            tier = name
    return tier

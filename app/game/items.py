"""Weapons, ammo, and healing items used by the in-memory match."""

WEAPONS = {
    "pistol": {
        "damage": 22.0,
        "range": 28.0,
        "mag": 12,
        "reload": 1.4,
        "cooldown": 0.35,
        "ammo": "light",
    },
    "rifle": {
        "damage": 16.0,
        "range": 70.0,
        "mag": 30,
        "reload": 2.2,
        "cooldown": 0.12,
        "ammo": "medium",
    },
}

HEALS = {"bandage": 20.0, "medkit": 60.0}

# item id, quantity per node, how many nodes to place
LOOT_TABLE = (
    ("pistol", 1, 4),
    ("rifle", 1, 4),
    ("light", 30, 8),
    ("medium", 30, 8),
    ("bandage", 2, 8),
    ("medkit", 1, 4),
)

MAX_WEAPONS = 2
MAX_STACK = 200


def is_weapon(item_id: str) -> bool:
    return item_id in WEAPONS


def weapon_count(inventory: dict[str, int]) -> int:
    return sum(1 for item_id, qty in inventory.items() if qty > 0 and item_id in WEAPONS)

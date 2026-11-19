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
    "smg": {
        "damage": 13.0,
        "range": 36.0,
        "mag": 32,
        "reload": 1.6,
        "cooldown": 0.08,
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
    "shotgun": {
        "damage": 42.0,
        "range": 16.0,
        "mag": 6,
        "reload": 2.4,
        "cooldown": 0.65,
        "ammo": "heavy",
    },
    "sniper": {
        "damage": 65.0,
        "range": 110.0,
        "mag": 5,
        "reload": 2.8,
        "cooldown": 1.1,
        "ammo": "heavy",
    },
}

HEALS = {"bandage": 20.0, "energy_drink": 35.0, "medkit": 60.0}

# Development vehicles. These numbers are not original Rules of Survival values.
VEHICLES = {
    "buggy": {"speed": 12.0, "seats": 1},
    "jeep": {"speed": 10.5, "seats": 4},
}

# item id, quantity per node, how many nodes to place
LOOT_TABLE = (
    ("pistol", 1, 4),
    ("smg", 1, 4),
    ("rifle", 1, 4),
    ("shotgun", 1, 3),
    ("sniper", 1, 3),
    ("light", 30, 8),
    ("medium", 30, 8),
    ("heavy", 12, 4),
    ("bandage", 2, 5),
    ("energy_drink", 1, 2),
    ("medkit", 1, 3),
)

MAX_WEAPONS = 2
MAX_STACK = 200


def is_weapon(item_id: str) -> bool:
    return item_id in WEAPONS


def weapon_count(inventory: dict[str, int]) -> int:
    return sum(1 for item_id, qty in inventory.items() if qty > 0 and item_id in WEAPONS)

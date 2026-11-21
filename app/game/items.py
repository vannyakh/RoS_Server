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
    "desert_eagle": {
        "damage": 40.0,
        "range": 32.0,
        "mag": 7,
        "reload": 1.8,
        "cooldown": 0.45,
        "ammo": "light",
    },
    "vector": {
        "damage": 11.0,
        "range": 34.0,
        "mag": 19,
        "reload": 1.5,
        "cooldown": 0.06,
        "ammo": "light",
    },
    "m14ebr": {
        "damage": 38.0,
        "range": 95.0,
        "mag": 10,
        "reload": 2.4,
        "cooldown": 0.45,
        "ammo": "medium",
    },
    "aa12": {
        "damage": 28.0,
        "range": 14.0,
        "mag": 8,
        "reload": 2.6,
        "cooldown": 0.2,
        "ammo": "heavy",
    },
    "awm": {
        "damage": 90.0,
        "range": 130.0,
        "mag": 5,
        "reload": 3.2,
        "cooldown": 1.5,
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

HEALS = {"bandage": 20.0, "energy_drink": 35.0, "medkit": 60.0, "first_aid": 80.0}
# Seconds the player spends using each item before it heals. Development numbers.
HEAL_TIME = {"bandage": 2.0, "energy_drink": 2.5, "medkit": 3.2, "first_aid": 5.0}

# Weapon slots: two primary weapons and one pistol, like the original loadout screen.
PISTOLS = frozenset({"pistol", "desert_eagle"})
SLOT_LIMITS = {"primary": 2, "pistol": 1}

# Attachments are consumed and fitted to the equipped weapon with the `attach` action.
ATTACHMENTS = {
    "scope_4x": {"range_mult": 1.25, "slots": ("primary",), "ammo": ("medium", "heavy")},
    "ext_mag": {"mag_bonus": 10, "slots": ("primary",), "ammo": ("light", "medium")},
}

# Wearable gear, levels 1 to 3. Development numbers, not original Rules of Survival values.
# Armor and helmet are damage reduction fractions applied one after the other.
ARMOR_REDUCTION = {1: 0.20, 2: 0.30, 3: 0.40}
HELMET_REDUCTION = {1: 0.10, 2: 0.15, 3: 0.20}
# Extra stack room per backpack level, on top of MAX_STACK.
BACKPACK_ROOM = {1: 100, 2: 200, 3: 300}
GEAR_SLOTS = ("armor", "helmet", "backpack")

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
    ("first_aid", 1, 2),
    ("desert_eagle", 1, 2),
    ("vector", 1, 2),
    ("m14ebr", 1, 2),
    ("aa12", 1, 2),
    ("awm", 1, 1),
    ("scope_4x", 1, 3),
    ("ext_mag", 1, 3),
    ("armor_1", 1, 3),
    ("armor_2", 1, 2),
    ("armor_3", 1, 1),
    ("helmet_1", 1, 3),
    ("helmet_2", 1, 2),
    ("helmet_3", 1, 1),
    ("backpack_1", 1, 3),
    ("backpack_2", 1, 2),
    ("backpack_3", 1, 1),
)

MAX_WEAPONS = 2
MAX_STACK = 200


def is_weapon(item_id: str) -> bool:
    return item_id in WEAPONS


def weapon_count(inventory: dict[str, int]) -> int:
    return sum(1 for item_id, qty in inventory.items() if qty > 0 and item_id in WEAPONS)


def gear_of(item_id: str) -> tuple[str, int] | None:
    """`armor_2` -> ("armor", 2). None for anything that is not wearable gear."""
    slot, _, level = item_id.rpartition("_")
    if slot not in GEAR_SLOTS or not level.isdigit():
        return None
    value = int(level)
    if value not in ARMOR_REDUCTION:
        return None
    return slot, value


def stack_limit(backpack: int) -> int:
    return MAX_STACK + BACKPACK_ROOM.get(backpack, 0)


def damage_after_gear(damage: float, armor: int, helmet: int) -> float:
    return damage * (1 - ARMOR_REDUCTION.get(armor, 0.0)) * (1 - HELMET_REDUCTION.get(helmet, 0.0))


def slot_of(item_id: str) -> str:
    return "pistol" if item_id in PISTOLS else "primary"


def slot_count(inventory: dict[str, int], slot: str) -> int:
    return sum(1 for item_id, qty in inventory.items() if qty > 0 and item_id in WEAPONS and slot_of(item_id) == slot)


def can_attach(attachment: str, weapon_id: str) -> bool:
    rule = ATTACHMENTS.get(attachment)
    weapon = WEAPONS.get(weapon_id)
    if rule is None or weapon is None:
        return False
    return slot_of(weapon_id) in rule["slots"] and weapon["ammo"] in rule["ammo"]

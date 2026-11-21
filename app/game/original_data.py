"""Optional access to original game data tables imported from a local OBB.

`python -m tools.original_data.import_tables <main.obb>` writes JSON under
`storage/original_data/` (git-ignored publisher data). Nothing here is required:
when the files are absent every loader returns an empty result and the match
loop keeps its own tuning. Table values are original data; the server's own
weapon numbers in `app/game/items.py` are not, and this module does not change them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "storage" / "original_data"


@lru_cache(maxsize=None)
def load_table(stem: str) -> dict:
    """Merged records of every imported table whose file name starts with `stem__`."""
    merged: dict = {}
    for path in sorted(DATA_DIR.glob(f"{stem}__*.json")):
        merged.update(json.loads(path.read_text(encoding="utf-8")).get("data", {}))
    return merged


def gun_mechanics() -> dict:
    """Recoil, scatter and aim tuning per gun record, keyed by record id as a string (empty when not imported)."""
    return {k: v.get("value", {}) for k, v in load_table("gun_mechanics").items()}


# Numeric fields of a battle prop's PROP_TYPE shown as stats: field -> (label, unit, multiplier, bar max).
# The bar max is a display scale for the admin, not a game limit. Fields not listed are left out.
_PROP_STAT_FIELDS: dict[str, tuple[str, str, float, float | None]] = {
    "AntiDamage": ("Damage reduction", "%", 100.0, 100.0),
    "DURABILITY": ("Durability", "", 1.0, 300.0),
    "LEVEL": ("Level", "", 1.0, 4.0),
    "EFFECT": ("Heal per use", "HP", 1.0, 100.0),
    "EFFECT_TIME": ("Heal time", "s", 1.0, None),
    "TIMES": ("Repeats", "", 1.0, None),
    "SPEED_ADD": ("Speed boost", "", 1.0, None),
    "FUEL_CAPACITY": ("Fuel", "", 1.0, None),
    "REPAIR_CAPACITY": ("Repair", "", 1.0, None),
    "INIT_BULLET_NUM": ("Starting ammo", "", 1.0, None),
    "DAMAGE_TO_VEHICLE_VALUE": ("Damage to vehicles", "", 1.0, 100.0),
    "DAMAGE_TO_VEHICLE_INTERVAL": ("Damage interval", "s", 1.0, None),
    "ADDED_MAXHP": ("Max HP bonus", "HP", 1.0, 100.0),
    "ENERGY": ("Energy", "", 1.0, None),
    "MAX_SPEED_ENHANCE_PERCENT": ("Top speed boost", "%", 1.0, 100.0),
    "TORQUE_ENHANCE_PERCENT": ("Torque boost", "%", 1.0, 100.0),
    "UP_FORCE": ("Jump force", "", 1.0, None),
    "BUFF_FACTOR": ("Buff factor", "x", 1.0, None),
    "DETECT_RANGE": ("Range", "", 1.0, None),
    "DURATION": ("Duration", "s", 1.0, None),
    "TIME": ("Duration", "s", 1.0, None),
    "CD_TIME": ("Cooldown", "s", 1.0, None),
}


def prop_stats(prop_id: int) -> list[dict]:
    """Display stats for one battle prop from the imported prop table ([] when not imported).

    Each row is {key, label, value, unit, max}: `key` is the original field name, `max` the bar
    scale or null. Gun attachments add one row per property modifier (factor in percent).
    """
    record = load_table("br_items").get(str(prop_id))
    if not record:
        return []
    prop_type = (record.get("value") or {}).get("PROP_TYPE") or {}
    fields = prop_type.get("value") or {}
    rows: list[dict] = []
    labels_used: set[str] = set()
    for key, (label, unit, multiplier, bar_max) in _PROP_STAT_FIELDS.items():
        value = fields.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or label in labels_used:
            continue
        labels_used.add(label)
        rows.append({"key": key, "label": label, "value": round(value * multiplier, 2), "unit": unit, "max": bar_max})
    for index, modifier in enumerate(fields.get("PROP_LIST") or []):
        factor = modifier.get("PROPERTY_FACTOR") if isinstance(modifier, dict) else None
        if isinstance(factor, (int, float)) and not isinstance(factor, bool):
            property_id = modifier.get("PROPERTY_ID")
            label = f"Property {property_id}" if property_id is not None else f"Modifier {index + 1}"
            rows.append({"key": "PROPERTY_FACTOR", "label": label, "value": round(factor * 100, 2), "unit": "%", "max": None})
    return rows

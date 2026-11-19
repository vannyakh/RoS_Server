"""Local pistol and rifle damage from app/game/items.py.

A hit subtracts WEAPONS damage from app/game/items.py. MatchRules in
app/game/rules.py supplies the hit radius. These numbers are this server's
rules. They are not original Rules of Survival combat values.

GP-007 Equipment stays not_implemented. GP-008 Vehicles stays a separate
matrix row whose compatibility_status is unknown. This file does not add
an equipment or vehicle combat contract.
"""

import inspect
import json
from pathlib import Path

from app.game.engine import GameEngine
from app.game.items import VEHICLES, WEAPONS
from app.game.rules import MatchRules
from app.game.simulate import simulate
from tools.game_simulator import ScenarioRunner

SEED = 7
ITEMS_SOURCE = "app/game/items.py"
RULES_SOURCE = "app/game/rules.py"
MATRIX_PATH = Path("testdata/reference/compatibility_matrix.json")
EXPECTED = json.loads(
    Path("testdata/expected_results/solo_elimination.json").read_text(encoding="utf-8")
)
MATRIX = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _feature(feature_id: str) -> dict:
    for feature in MATRIX["features"]:
        if feature["feature_id"] == feature_id:
            return feature
    raise AssertionError(f"{feature_id} is missing from {MATRIX_PATH.as_posix()}")


def _fast_rules() -> MatchRules:
    return MatchRules(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100)


async def _playing_pair(rules: MatchRules) -> GameEngine:
    engine = GameEngine(rules)
    await engine.join_queue("alpha")
    await engine.join_queue("bravo")
    await engine.step(0.05)
    return engine


def _place_in_front(engine: GameEngine, rules: MatchRules) -> None:
    alpha = engine.world.players["alpha"]
    bravo = engine.world.players["bravo"]
    weapon = WEAPONS[alpha.weapon or ""]
    bravo.x = alpha.x + min(2.0, float(weapon["range"]))
    bravo.y = alpha.y
    alpha.aim_x = 1.0
    alpha.aim_y = 0.0
    assert abs(bravo.x - alpha.x) <= float(weapon["range"])
    assert abs(bravo.y - alpha.y) <= rules.hit_radius


async def test_pistol_damage_cites_items_py():
    """One pistol hit subtracts WEAPONS pistol damage from app/game/items.py."""
    pistol_damage = WEAPONS["pistol"]["damage"]
    assert pistol_damage == 22.0, f"{ITEMS_SOURCE} pistol damage is the local combat rule"
    rules = _fast_rules()
    assert rules.hit_radius == 1.25, f"{RULES_SOURCE} MatchRules.hit_radius places the hit"
    engine = await _playing_pair(rules)
    _place_in_front(engine, rules)
    before = engine.world.players["bravo"].health
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert ok is True and detail == "Hit"
    assert engine.world.players["bravo"].health == before - pistol_damage
    assert engine.world.players["alpha"].weapon == "pistol"


async def test_rifle_damage_cites_items_py():
    """One rifle hit subtracts WEAPONS rifle damage from app/game/items.py."""
    rifle_damage = WEAPONS["rifle"]["damage"]
    assert rifle_damage == 16.0, f"{ITEMS_SOURCE} rifle damage is the local combat rule"
    assert rifle_damage != WEAPONS["pistol"]["damage"]
    rules = _fast_rules()
    engine = await _playing_pair(rules)
    alpha = engine.world.players["alpha"]
    alpha.inventory["rifle"] = 1
    alpha.mags["rifle"] = int(WEAPONS["rifle"]["mag"])
    ok, detail = await engine.perform("alpha", "equip", None, "rifle")
    assert ok is True and detail == "Equipped rifle"
    assert alpha.weapon == "rifle"
    _place_in_front(engine, rules)
    before = engine.world.players["bravo"].health
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert ok is True and detail == "Hit"
    assert engine.world.players["bravo"].health == before - rifle_damage


async def test_weapon_scenario_is_deterministic_and_not_original_combat():
    """The same seed eliminates with this server's pistol rule, twice."""
    assert WEAPONS["pistol"]["damage"] == 22.0
    assert ITEMS_SOURCE in EXPECTED["source"]
    first = await ScenarioRunner().run(SEED)
    second = await ScenarioRunner().run(SEED)
    assert first.winner_id == second.winner_id
    assert first.stats == second.stats
    assert first.movement_delta == second.movement_delta
    assert first.winner_id == EXPECTED["winner_id"]
    assert first.stats == EXPECTED["stats"]
    tick_source = inspect.getsource(GameEngine.step) + inspect.getsource(simulate)
    assert "Session" not in tick_source
    assert "database" not in tick_source


def test_equipment_and_vehicles_stay_outside_this_weapon_contract():
    """GP-007 stays not implemented. Both compatibility rows stay unknown.

    testdata/reference/compatibility_matrix.json records GP-008 as
    implemented. This test does not edit that row and does not treat vehicle
    speed as pistol or rifle damage. Original compatibility stays unknown.
    """
    equipment = _feature("GP-007")
    vehicles = _feature("GP-008")
    assert equipment["function_name"] == "Equipment"
    assert equipment["implementation_status"] == "not_implemented"
    assert equipment["compatibility_status"] == "unknown"
    assert vehicles["function_name"] == "Vehicles"
    assert vehicles["compatibility_status"] == "unknown"
    assert vehicles["implementation_status"] == "implemented", (
        "GP-008 stays the local vehicle row already stored in the matrix; "
        "compatibility_status stays unknown and this file adds no vehicle contract"
    )
    assert "damage" not in VEHICLES["buggy"]
    assert "damage" not in VEHICLES["jeep"]
    for feature in MATRIX["features"]:
        if feature["feature_id"] in {"GP-004", "GP-005", "GP-007", "GP-008"}:
            assert feature["compatibility_status"] == "unknown"


async def test_equipping_a_non_weapon_does_not_create_an_equipment_contract():
    """Armor is not a weapon. The match loop refuses it."""
    engine = await _playing_pair(_fast_rules())
    ok, detail = await engine.perform("alpha", "equip", None, "helmet")
    assert ok is False and detail == "Not a weapon"
    assert engine.world.players["alpha"].weapon == "pistol"

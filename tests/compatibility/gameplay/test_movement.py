"""Local on-foot movement from app/game/rules.py.

ScenarioRunner steps one second of unit input. The position change equals
MatchRules.speed in app/game/rules.py. That speed is this server's rule.
It is not an original Rules of Survival movement value.

app/game/items.py vehicle speeds are a separate development table. They are
not the on-foot delta this test records. GP-002 stays unknown.
"""

import inspect
import json
from pathlib import Path

from app.game.engine import GameEngine
from app.game.items import VEHICLES
from app.game.rules import MatchRules
from app.game.simulate import simulate
from tools.game_simulator import ScenarioRunner

SEED = 7
RULES_SOURCE = "app/game/rules.py"
EXPECTED = json.loads(
    Path("testdata/expected_results/solo_elimination.json").read_text(encoding="utf-8")
)
MATRIX = json.loads(
    Path("testdata/reference/compatibility_matrix.json").read_text(encoding="utf-8")
)


def _gp002_row() -> dict | None:
    for feature in MATRIX["features"]:
        if feature["feature_id"] == "GP-002":
            return feature
    return None


async def test_on_foot_delta_cites_match_rules_speed():
    """One second of input moves MatchRules.speed from app/game/rules.py."""
    rules = MatchRules()
    foot_speed = rules.speed
    assert foot_speed == 5.0, f"{RULES_SOURCE} MatchRules.speed is the on-foot contract"
    vehicle_speeds = {kind: float(row["speed"]) for kind, row in VEHICLES.items()}
    assert foot_speed not in vehicle_speeds.values(), (
        f"on-foot speed comes from {RULES_SOURCE}; "
        "app/game/items.py vehicle speeds are a different table"
    )

    first = await ScenarioRunner().run(SEED)
    second = await ScenarioRunner().run(SEED)
    assert first.winner_id == second.winner_id
    assert first.stats == second.stats
    assert first.movement_delta == second.movement_delta

    assert first.movement_delta == foot_speed, (
        "movement_delta equals MatchRules.speed for one second of unit input; "
        f"source file {RULES_SOURCE}; not an original RoS movement value"
    )
    assert first.movement_delta == EXPECTED["movement_delta"]
    assert RULES_SOURCE in EXPECTED["source"]
    assert first.winner_id == EXPECTED["winner_id"]
    assert first.stats == EXPECTED["stats"]

    tick_source = inspect.getsource(GameEngine.step) + inspect.getsource(simulate)
    assert "Session" not in tick_source
    assert "database" not in tick_source

    row = _gp002_row()
    assert row is not None, "GP-002 is present in testdata/reference/compatibility_matrix.json"
    assert row["compatibility_status"] == "unknown", (
        "GP-002 compatibility_status stays unknown; "
        "a local speed check is not original RoS movement"
    )

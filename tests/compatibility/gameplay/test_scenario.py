import json
from pathlib import Path

from tools.game_simulator import ScenarioRunner, StateValidator

EXPECTED = json.loads(Path("testdata/expected_results/solo_elimination.json").read_text(encoding="utf-8"))
SCENARIO = json.loads(Path("testdata/scenarios/solo_elimination.json").read_text(encoding="utf-8"))


async def test_seeded_scenario_follows_server_rules():
    first = await ScenarioRunner().run(SCENARIO["seed"])
    second = await ScenarioRunner().run(SCENARIO["seed"])
    StateValidator().validate(first, EXPECTED)
    assert first.stats == second.stats
    assert first.winner_id == second.winner_id
    assert "persist_results" in first.steps
    assert first.results["alpha"]["placement"] == 1

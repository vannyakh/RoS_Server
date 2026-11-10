import json
from pathlib import Path

from tools.game_simulator import ScenarioRunner

EXPECTED = json.loads(Path("testdata/expected_results/solo_elimination.json").read_text(encoding="utf-8"))


async def test_results_record_placement_kills_and_totals():
    result = await ScenarioRunner().run(7)
    assert result.winner_id == EXPECTED["winner_id"]
    assert result.results["alpha"]["kills"] == 1
    assert result.results["alpha"]["placement"] == 1
    assert result.results["bravo"]["win"] is False
    assert result.stats == EXPECTED["stats"]

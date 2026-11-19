"""Local match results from app/game/state.py and app/game/simulate.py.

The in-memory MatchResult fields are player_id, kills, win, and placement.
app/schemas/match.py MatchResultCreate can store a rewards object. This
simulation does not grant experience or currency from that object, and it
does not write player progression. Pistol damage comes from app/game/items.py.
On-foot speed comes from app/game/rules.py. Those figures are this server's
rules. They are not original Rules of Survival reward values.

RS-001, RS-002, and RS-003 are the tests in this file.
RS-004, RS-005, and RS-006 stay not_implemented. compatibility_status stays
unknown for every results row.
"""

import inspect
import json
from dataclasses import fields
from pathlib import Path

import app.game.simulate as simulation
from app.game.engine import GameEngine
from app.game.items import WEAPONS
from app.game.rules import MatchRules
from app.game.state import MatchResult
from app.schemas.match import MatchResultCreate
from app.services.match_service import MatchService
from app.services.persistence_service import PersistenceService
from tools.game_simulator import ScenarioRunner

SEED = 7
STATE_SOURCE = "app/game/state.py"
ITEMS_SOURCE = "app/game/items.py"
RULES_SOURCE = "app/game/rules.py"
MATRIX_PATH = Path("testdata/reference/compatibility_matrix.json")
RESULT_FIELDS = ("player_id", "kills", "win", "placement")
REWARD_IDS = ("RS-004", "RS-005", "RS-006")
LOCAL_IDS = ("RS-001", "RS-002", "RS-003")

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
    return MatchRules(
        bot_fill=0,
        queue_wait=0,
        countdown=0,
        drop_time=0,
        phase_duration=100,
        result_time=100,
    )


async def _playing(player_ids: tuple[str, ...]) -> GameEngine:
    engine = GameEngine(_fast_rules())
    for player_id in player_ids:
        ok, detail = await engine.join_queue(player_id)
        assert ok is True, detail
    await engine.step(0.05)
    match = next(iter(engine.world.matches.values()))
    assert match.phase == "playing"
    return engine


async def _shoot_until_down(engine: GameEngine, shooter_id: str, target_id: str) -> int:
    shots = 0
    target = engine.world.players[target_id]
    while target.status != "eliminated" and shots < 8:
        ok, detail = await engine.perform(shooter_id, "shoot", None, None)
        assert ok is True, detail
        shots += 1
        await engine.step(float(WEAPONS["pistol"]["cooldown"]))
    assert target.status == "eliminated"
    return shots


def _result_map(results: list[MatchResult]) -> dict[str, MatchResult]:
    return {item.player_id: item for item in results}


async def test_results_record_placement_kills_and_totals():
    result = await ScenarioRunner().run(SEED)
    assert result.winner_id == EXPECTED["winner_id"]
    assert result.results["alpha"]["kills"] == 1
    assert result.results["alpha"]["placement"] == 1
    assert result.results["bravo"]["win"] is False
    assert result.stats == EXPECTED["stats"]


async def test_rs001_match_completion_ends_when_one_combatant_remains():
    """RS-001. The phase becomes ended when one combatant remains.

    Source: app/game/simulate.py _maybe_finish sets phase to ended and
    records the winner. The same seed repeats that winner.
    """
    row = _feature("RS-001")
    assert row["function_name"] == "Match completion"
    assert row["implementation_status"] == "implemented"
    assert row["compatibility_status"] == "unknown"
    assert row["evidence"] == "tests/compatibility/match_results/test_results.py"
    assert row["original_reference"].startswith("No authorized")

    engine = await _playing(("alpha", "bravo"))
    await _shoot_until_down(engine, "alpha", "bravo")
    match = next(iter(engine.world.matches.values()))
    assert match.phase == "ended"
    assert match.winner_id == "alpha"
    assert engine.world.players["alpha"].status == "winner"
    assert len([player for player in engine.world.players.values() if player.status == "alive"]) == 0

    finish_source = inspect.getsource(simulation._maybe_finish)
    assert 'match.phase = "ended"' in finish_source
    assert "winner_id" in finish_source

    first = await ScenarioRunner().run(SEED)
    second = await ScenarioRunner().run(SEED)
    assert first.seed == SEED
    assert first.winner_id == second.winner_id == EXPECTED["winner_id"]
    assert "end_match" in first.steps
    assert first.stats == second.stats == EXPECTED["stats"]


async def test_rs002_placement_follows_local_elimination_order():
    """RS-002. Winner is place 1. Later eliminations take the next places.

    Source: app/game/state.py MatchResult.placement and
    app/game/simulate.py _record_results. Last eliminated human is place 2.
    """
    row = _feature("RS-002")
    assert row["function_name"] == "Placement"
    assert row["implementation_status"] == "implemented"
    assert row["compatibility_status"] == "unknown"
    assert row["evidence"] == "tests/compatibility/match_results/test_results.py"

    engine = await _playing(("alpha", "bravo", "charlie"))
    await _shoot_until_down(engine, "alpha", "bravo")
    await _shoot_until_down(engine, "alpha", "charlie")
    match = next(iter(engine.world.matches.values()))
    assert match.elimination_order == ["bravo", "charlie"]
    assert match.phase == "ended"
    assert match.winner_id == "alpha"

    results = _result_map(await engine.take_results())
    assert results["alpha"].placement == 1
    assert results["alpha"].win is True
    assert results["charlie"].placement == 2
    assert results["charlie"].win is False
    assert results["bravo"].placement == 3
    assert results["bravo"].win is False

    record_source = inspect.getsource(simulation._record_results)
    assert "placement[match.winner_id] = 1" in record_source
    assert "reversed(match.elimination_order)" in record_source
    assert "experience" not in record_source
    assert "currency" not in record_source
    assert tuple(item.name for item in fields(MatchResult)) == RESULT_FIELDS


async def test_rs003_kills_count_shot_eliminations():
    """RS-003. A shot elimination adds one kill. A zone elimination does not.

    Damage per pistol hit is WEAPONS pistol damage in app/game/items.py.
    app/game/rules.py MatchRules.hit_radius places the hit. A zone elimination
    passes no killer, so kills stay 0. This is not an original RoS kill value.
    """
    row = _feature("RS-003")
    assert row["function_name"] == "Kill statistics"
    assert row["implementation_status"] == "implemented"
    assert row["compatibility_status"] == "unknown"
    assert row["evidence"] == "tests/compatibility/match_results/test_results.py"

    pistol_damage = WEAPONS["pistol"]["damage"]
    assert pistol_damage == 22.0, f"{ITEMS_SOURCE} pistol damage is the local shot rule"
    rules = _fast_rules()
    assert rules.hit_radius == 1.25, f"{RULES_SOURCE} MatchRules.hit_radius places the hit"
    assert ITEMS_SOURCE in EXPECTED["source"]

    engine = await _playing(("alpha", "bravo"))
    bravo = engine.world.players["bravo"]
    health_before = bravo.health
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert ok is True and detail == "Hit"
    assert bravo.health == health_before - pistol_damage
    assert engine.world.players["alpha"].kills == 0
    await engine.step(float(WEAPONS["pistol"]["cooldown"]))
    shots = 1 + await _shoot_until_down(engine, "alpha", "bravo")
    assert shots * pistol_damage >= health_before
    results = _result_map(await engine.take_results())
    assert results["alpha"].kills == 1
    assert results["bravo"].kills == 0
    assert results["alpha"].placement == 1
    assert results["bravo"].placement == 2

    zone = await _playing(("alpha", "bravo"))
    match = next(iter(zone.world.matches.values()))
    alpha = zone.world.players["alpha"]
    bravo = zone.world.players["bravo"]
    match.zone_x = alpha.x
    match.zone_y = alpha.y
    match.zone_radius = 1.0
    match.zone_dps = 50.0
    bravo.health = 10.0
    await zone.step(1)
    assert bravo.status == "eliminated"
    assert alpha.kills == 0
    assert match.phase == "ended"
    assert match.winner_id == "alpha"
    zone_results = _result_map(await zone.take_results())
    assert zone_results["alpha"].kills == 0
    assert zone_results["bravo"].kills == 0
    assert zone_results["alpha"].placement == 1

    eliminate_source = inspect.getsource(simulation._eliminate)
    assert "killer.kills += 1" in eliminate_source
    shoot_source = inspect.getsource(simulation._shoot)
    assert '"shot"' in shoot_source
    zone_source = inspect.getsource(simulation._apply_zone)
    assert '"zone"' in zone_source


async def test_seeded_local_results_repeat_and_omit_rewards():
    """Same seed, same winner, placement, kills, movement delta, and totals.

    The tick that produces the result does not open a database session.
    """
    rules = MatchRules()
    assert rules.speed == 5.0, f"{RULES_SOURCE} MatchRules.speed is the on-foot rule"
    assert RULES_SOURCE in EXPECTED["source"]

    first = await ScenarioRunner().run(SEED)
    second = await ScenarioRunner().run(SEED)
    assert first.winner_id == second.winner_id == "alpha"
    assert first.movement_delta == second.movement_delta == rules.speed
    assert first.movement_delta == EXPECTED["movement_delta"]
    assert first.stats == second.stats == EXPECTED["stats"]
    assert first.results == second.results
    assert first.results["alpha"] == {"kills": 1, "win": True, "placement": 1}
    assert first.results["bravo"] == {"kills": 0, "win": False, "placement": 2}
    for row in first.results.values():
        assert set(row) == {"kills", "win", "placement"}
        assert "experience" not in row
        assert "currency" not in row
        assert "rewards" not in row

    names = tuple(item.name for item in fields(MatchResult))
    assert names == RESULT_FIELDS, f"{STATE_SOURCE} MatchResult fields are the local result"
    assert "experience" not in names
    assert "currency" not in names
    assert "rewards" not in names

    stored = MatchResultCreate(player_id="alpha", placement=1, kills=1)
    assert stored.placement == 1
    assert stored.kills == 1
    assert stored.rewards == {}
    assert "rewards" in MatchResultCreate.model_fields
    assert "experience" not in MatchResultCreate.model_fields
    assert "currency" not in MatchResultCreate.model_fields

    finalize_source = inspect.getsource(MatchService.finalize)
    assert "rewards=dict(result.get(\"rewards\") or {})" in finalize_source
    assert "experience" not in finalize_source
    assert "apply_currency" not in finalize_source
    assert "PlayerProgression" not in finalize_source
    progress_source = inspect.getsource(PersistenceService.save_player_progress)
    assert "total_kills" in progress_source
    assert "experience" not in progress_source
    assert "currency" not in progress_source
    assert "progression" not in progress_source

    tick_source = inspect.getsource(GameEngine.step) + inspect.getsource(simulation.simulate)
    assert "Session" not in tick_source
    assert "database" not in tick_source
    module_source = inspect.getsource(simulation)
    assert "SessionLocal" not in module_source


def test_rs004_rs005_rs006_stay_not_implemented():
    """Reward rows stay not implemented. compatibility_status stays unknown.

    This test reads testdata/reference/compatibility_matrix.json. It does not
    change those rows and it does not grant experience, currency, or progression.
    """
    expected = {
        "RS-004": {
            "function_name": "Experience rewards",
            "known_differences": (
                "No experience is granted at match end. A rewards object on a "
                "stored result is saved and not applied. Repeating finalization is rejected."
            ),
        },
        "RS-005": {
            "function_name": "Currency rewards",
            "known_differences": (
                "Currency tables exist. Match completion does not pay them, "
                "including when the result payload names a currency amount."
            ),
        },
        "RS-006": {
            "function_name": "Player progression",
            "known_differences": "Progression rows are not written from match results.",
        },
    }
    for feature_id, spec in expected.items():
        row = _feature(feature_id)
        assert row["function_name"] == spec["function_name"]
        assert row["implementation_status"] == "not_implemented"
        assert row["compatibility_status"] == "unknown"
        assert row["known_differences"] == spec["known_differences"]
        assert row["original_reference"].startswith("No authorized")

    for feature_id in LOCAL_IDS + REWARD_IDS:
        assert _feature(feature_id)["compatibility_status"] == "unknown"

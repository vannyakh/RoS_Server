---
name: gameplay-testing
description: Runs the deterministic match scenario against app.game rules. Use when movement, weapons, elimination, or match results change.
---

# Gameplay testing

## Workflow

1. Call `ScenarioRunner().run(seed)` from `tools.game_simulator`.
2. Compare the result with `testdata/expected_results/solo_elimination.json`.
3. Run the same seed twice and require the same winner and totals.
4. Cite `app/game/items.py` for damage and `app/game/rules.py` for speed.

## Output

Seed, winner, movement delta, and statistics.

## Failure

If two seeds disagree, stop and fix the non-deterministic step. Do not mark the scenario as original RoS behavior.

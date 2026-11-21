---
name: jev-game-explorer
description: Explores the survival match (parachute, loot, gear, squads, knock-down, zone) with the local simulator and asks the jev.ai assistant for second opinions, caching answers. Use when an agent needs to learn how the game behaves or find gaps before changing app/game.
---

# jev.ai game explorer

Owner: `gameplay-test-engineer`. Rule: `.cursor/rules/14-gameplay-testing.mdc`. Take the task from `.cursor/management/tasks.json` and write only its `files_allowed`.

## When

Before changing `app/game`, or when a match behaves in a way the docs do not explain.

## Input

A question about the game. The key lives only in `.env` as `JEV_API_KEY`. Also set `JEV_BASE_URL` (and `JEV_PATH`, `JEV_AUTH_HEADER`, `JEV_AUTH_SCHEME`, `JEV_PROMPT_FIELD`, `JEV_ANSWER_FIELD` if the jev.ai documentation differs from the defaults in `tools/jev_assist/client.py`). Never print, paste, or commit the key.

## Workflow

1. Read `docs/GAMEPLAY_SYSTEMS.md`, then `app/game/rules.py`, `app/game/items.py` and `app/game/simulate.py` for the rule in question.
2. Reproduce it with `GameEngine(MatchRules(bot_fill=0, queue_wait=0, countdown=0, drop_time=0))` as in `tests/unit/test_survival.py` and `tests/unit/test_squads.py`. Place players explicitly so a teammate is not in the line of fire.
3. Ask jev.ai only for ideas and edge cases. Answers are saved in `.cache/jev` (git-ignored); a repeated question is served from there without the key:

```powershell
python -m tools.jev_assist "What edge cases break revive when the reviver is shot?"
python -m tools.jev_assist --refresh "same question"
```

4. Treat every answer as a hypothesis. Confirm it with a test before it becomes a rule, and label numbers as this server's own design, not original Rules of Survival values.

## Exploration checklist

Parachute landing and `Still parachuting`; death crate contents; stack limits with a backpack; armor and helmet math; knock, bleed-out, revive cancel; friendly fire; last squad wins; zone damage to a knocked player; re-queue while the old match runs.

## Output

The question, the test or script that checked it, what the match did, and any gap found. Quote no key and no raw API response.

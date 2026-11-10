---
name: game-compatibility
description: Updates the RoS compatibility matrix from evidence. Use when a feature's original-server status, implementation status, or test evidence changes.
---

# Game compatibility

## Workflow

1. Open `testdata/reference/compatibility_matrix.json`.
2. Set `implementation_status` from the code you opened: `implemented`, `partial`, or `not_implemented`.
3. Set `test_status` to `passing` only when the cited test passed in this session.
4. Leave `compatibility_status` as `unknown` unless `original_reference` names an authorized source and the test ran against it.
5. Run `audit(load_matrix())` from `tools.compatibility_checker`. It must return no problems.
6. Regenerate `docs/compatibility/GAME_COMPATIBILITY_MATRIX.md` with `render_markdown`.

## Output

The updated row and the three counts: implemented, tests passing, and original-compatible.

## Failure

If the only evidence is a local simulation, keep compatibility `unknown`.

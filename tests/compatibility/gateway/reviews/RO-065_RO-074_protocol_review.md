TASK ID: RO-065, RO-074
AGENT: protocol-test-engineer
PHASE: testing (protocol / wire review)
STATUS: review complete

IMPLEMENTATION:
Research deliverables from game-compatibility-engineer. Protocol scope only: client→server cell methods, framing, and gateway `battle_flow.Match.handle` echo behaviour documented in the markdown + extract JSON.

FILES CREATED:
tests/compatibility/gateway/reviews/RO-065_RO-074_protocol_review.md

FILES MODIFIED:
(none)

DISCOVERIES:
- `DtsProp.tryPickUp`: exposed index **1**, msg **`0x81`**, payload `eid u32` + `INT32` + `BOOL`; capture `810900477500000100000001` matches `battle_cell_exposed.json` `_captures` and `test_battle_requests.test_try_pickup_from_capture`.
- `BattleGroundSpace.openElement` / `closeElement`: indices **8** / **9**, msg **`0x88`** / **`0x89`**; captures match `test_battle_requests` and `encode_call` round-trip for open.
- `battle_flow.decode_request` applies `EXPOSED_SHIFT` only to `BattleGroundAvatar`; `DtsProp` and `BattleGroundSpace` use raw exposed indices — consistent with LOOT_AND_PICKUP.md §4.1 and DOORS_AND_ELEMENTS.md §1.
- All ten `propID` rows in LOOT_AND_PICKUP.md §2.2 exist in `server/extract/battle_props.json`; `map700_loot.json` lists the same ten ids with `_position_source: gateway-authored`.

DATABASE CHANGES:
none

API CHANGES:
none

GAME FUNCTION CHANGES:
none (review only)

TESTS EXECUTED:
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/requests/test_battle_requests.py -q --tb=line
python -c "import json; json.load(open('bigworld_gateway/server/extract/map700_loot.json', encoding='utf-8')); json.load(open('bigworld_gateway/server/extract/map700_elements.json', encoding='utf-8'))"
python scripts/validate_agent_registry.py
python scripts/validate_project_management.py

TEST RESULTS:
15 passed in 0.29s (test_battle_requests.py)
JSON load: OK (map700_loot.json, map700_elements.json)
validate_agent_registry.py: OK: 13 agents, 127 tasks
validate_project_management.py: OK: 127 tasks, 12 discoveries, 43 compatibility features

COMPATIBILITY EVIDENCE:
Passing decode tests and captured hex are **gateway wire evidence only**, not original NetEase server proof. Deliverables state `compatibility_status: unknown` appropriately.

KNOWN ISSUES:
- RO-074 task acceptance (game-compatibility): §8 building matrix is **elem 832 only**; `map700_elements.json` `buildings[]` is empty; AC4 live LDPlayer captures not attached (noted in tasks.json `test_evidence`).
- RO-074: outbound `onElementOpen` server→client bytes not captured (documented §9-D); `openedElements` property not written on gateway (documented §2).

RECOMMENDATION:

## RO-065 — **APPROVE** (protocol + research deliverables)

Wire and pickup documentation align with `battle_cell_exposed.json`, hex fixtures, `battle_flow.py` `Match.handle` tryPickUp branch, and existing pytest decode coverage. Ten `propID` examples are backed by `battle_props.json`. `map700_loot.json` is valid, data-only, gateway-authored.

## RO-074 — **DEFECTS** (task acceptance); **APPROVE** (documented wire contract)

| Area | Verdict |
|------|---------|
| `0x88` / `0x89` framing, elem 832 captures, gateway echo in `battle_flow.py` | **Verified** — same as RO-057 tests |
| Per-building table, ≥3 buildings / double door / failure logs (AC1, AC4) | **Missing** — not blocking wire truth; blocks **completed** until game-compatibility fills §8 and `buildings[]` |

CTO may move RO-065 past protocol sign-off. Hold RO-074 **completed** until building matrix + live log evidence; wire docs need no correction.

OBJECTIVE:
Review RO-065 and RO-074 `testing` deliverables; verify wire claims against `battle_cell_exposed.json` and `battle_flow.py`.

IMPLEMENTATION SUMMARY:
Read LOOT_AND_PICKUP.md, DOORS_AND_ELEMENTS.md, extract JSON, battle_flow handle/decode paths, and `test_battle_requests.py` (including tryPickUp `0x81`). No test edits (task `files_allowed` for RO-065/074 exclude `tests/**`).

SECURITY CONSIDERATIONS:
none

DEPENDENCIES:
RO-057 decode fixtures (test_battle_requests.py)
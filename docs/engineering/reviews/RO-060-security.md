TASK ID: RO-060
AGENT: security-engineer
PHASE: 09 read-only in-battle request decoder review
STATUS: report written

IMPLEMENTATION: No application code, tests, migrations, environment files, or task registry files were modified.
FILES CREATED: docs/engineering/reviews/RO-060-security.md
FILES MODIFIED: none
DISCOVERIES: `bigworld_gateway/server/battle/requests.py` decodes named cell methods with bounds and never-raise paths. `0xBC`/`0xBD` are cell-method msgids, not position. `PositionTracker` / `decode_position` do not invent xyz. Module is not imported by `ros_server.py` or `battle/modules/`.
DATABASE CHANGES: none
API CHANGES: none
GAME FUNCTION CHANGES: none
TESTS EXECUTED: `.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/requests -q --tb=line`
TEST RESULTS: 15 passed in 0.27s
COMPATIBILITY EVIDENCE: none claimed. This review does not mark any feature original-compatible.
KNOWN ISSUES: Decoder not wired into the gateway receive path. Entity ids are only u32-masked. Once-only log keys can grow with unique truncated hex. Arg lengths are not checked against `.def` signatures.
RECOMMENDATION: pass

OBJECTIVE: Read-only security review of the RO-060 in-battle request decoder for untrusted bytes, logging, `0xBC`/`0xBD` confusion, and residual risk when wired.
IMPLEMENTATION SUMMARY: Inspected `bigworld_gateway/server/battle/requests.py` and `tests/compatibility/gateway/requests/**`. Confirmed framing bounds, exception swallowing, method-vs-position handling, and that no secrets appear in log strings from this module.
SECURITY CONSIDERATIONS: Findings cite opened files only. No JWT secret, raw token, password hash, or `.env` value is included. Severity labels are critical, high, and medium. No critical or high finding.
DEPENDENCIES: This report does not change task status. Wiring into `ros_server` / `MatchSession` remains a later change and needs a fresh security pass on the dispatch handlers.

# RO-060 in-battle request decoder

Reviewer: security-engineer. Scope was read-only.

## Scope read

- `bigworld_gateway/server/battle/requests.py`
- `tests/compatibility/gateway/requests/test_battle_requests.py`
- `tests/compatibility/gateway/requests/conftest.py`
- `bigworld_gateway/server/extract/battle_cell_exposed.json` (header / `_captures` only, for msgid and shift context)
- Search of `bigworld_gateway/server/ros_server.py` and `bigworld_gateway/server/battle/modules/` for imports of `battle.requests` / `decode_frame` (none found)

## Findings

### Medium — once-only log key set can grow without bound

**Confirmed fact.** `bigworld_gateway/server/battle/requests.py` stores once-only keys in module-global `_unknown_logged`. Truncated-frame keys embed `_hex_preview(data)` (`frame:trunc:…`), so each distinct truncated blob adds a new key.

**Confirmed fact.** There is no max size or TTL on `_unknown_logged`. `reset_log_state()` clears it for tests only.

**Interpretation.** While this helper is unwired, impact is low. After wiring to a live receive loop, a client that floods unique truncated frames can grow process memory via the set. Prefer keys that omit raw hex (msgid + reason + length only) before production wiring.

### Medium — entity id is masked, not session-scoped

**Confirmed fact.** `_clamp_eid` in `requests.py` returns `int(raw) & MAX_ENTITY_ID` (`0xFFFFFFFF`). `entity_type_of` maps space `20001`, plane `20002`, props `>= PROP_ID_BASE`, else `BattleGroundAvatar`.

**Confirmed fact.** Decode accepts any u32 eid and returns a `CellCall` with that id. No check that the eid was allocated by `MatchSession` or owned by the sender.

**Interpretation.** Acceptable for a pure decoder. When wired, handlers must re-validate eid ownership / existence before applying `openElement`, `tryPickUp`, avatar methods, or similar. Trusting `CellCall.entity_id` alone would allow cross-entity confusion.

### No critical / high findings

No critical or high finding in the files read.

## Checklist results

### Untrusted client bytes

**Confirmed fact.** `MSGID_MIN`/`MSGID_MAX` gate msgids to `0x80`–`0xBF`. `_bound_len` / `MAX_VAR16_LEN` cap declared length. `decode` rejects payload length `> MAX_VAR16_LEN` and payload shorter than 4 bytes. Extended paths require a sub-byte. Outer `try`/`except` in `decode` and `decode_frame` return `None` and log once.

**Confirmed fact.** Tests in `test_battle_requests.py` cover empty, msgid-only, length-without-payload, truncated eid, extended-missing-sub, oversized declared length, oversized payload buffer, unknown msgid, and unknown index — all expect `None` and one log line, no exception. Pytest: 15 passed.

### Logging and secrets

**Confirmed fact.** Log lines use `[BATTLE]` prefixes, msgid, eid, entity class, method index, and hex previews capped at `MAX_LOG_HEX` (64). No reference to JWT, password, token, or `.env` values appears in `requests.py`.

**Confirmed fact.** Successful decode does not call `log`. Error / unknown paths may hex-dump untrusted game payload bytes (game protocol, not account tokens in this framing).

**Interpretation.** Logging does not leak account secrets from this module. When wired, callers should continue to avoid dumping auth material into the same `log` callback.

### `0xBC` / `0xBD` are methods, not position

**Confirmed fact.** Module docstring and `PositionTracker` state that `0xBC`/`0xBD` are Avatar extended cell-method ids; position uses ClientInterface msg `3` with `POSITION_LAYOUT_STATUS = "unknown"`.

**Confirmed fact.** `test_msg_0xbc_is_cell_method_not_position` decodes `0xBC` to `onRecvClientFPS` and shows `decode_position(0xBC, …)` leaves `tracker.status == "unknown"` and `tracker.last is None`. `test_request_get_off_plane_shift_and_length_quirk` and parachute/glider tests use msgid `0xBC` as methods. `decode_position` only notes msg `3` and never parses xyz.

**Interpretation.** No DoS/confusion path in this helper that treats `0xBC`/`0xBD` as a position channel.

### Not wired to ros_server

**Confirmed fact.** `ros_server.py` imports and uses `athlete_requests` for lobby decode. A search for `battle.requests`, `decode_frame`, and related names under `bigworld_gateway/server/ros_server.py` and `bigworld_gateway/server/battle/modules/` found no consumer. Task evidence also notes the decode helper is not on the receive path yet.

## Residual risk (when wired)

1. **Dispatch trust.** Named `CellCall` values must not drive world mutation until the session checks eid ownership, match state, and arg sanity.
2. **Arg lengths.** Trailing bytes are kept for the `requestGetOffPlane` quirk; `.def` arity is not enforced. Handlers must not assume args match the extract signature.
3. **Log-key growth.** Replace hex-in-key once-only logging before exposing the decoder to untrusted high-rate traffic.
4. **Position still unknown.** No safe xyz yet; modules must not invent position from cell-method msgids.
5. **Process boundary.** Gateway must keep using `/api/v1/gateway` for persistence; this decoder must not open `app/` or the live SQLite file.

## Recommendation to CTO

**RECOMMENDATION: pass**

The RO-060 decoder meets the security bar for an unwired, never-raise bounded helper: length/msgid gates, no exception escape on truncated/oversized/unknown input, no secret leakage in its log strings, and `0xBC`/`0xBD` treated as cell methods. Medium items are residual wiring hygiene, not blockers for this review.

Do not claim original-client or original-server compatibility from this review.

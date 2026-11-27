# Player movement (restoration notes)

**Original APK:** Client drives physics; server echoes state where captures show replies (`changePose` → `pose`, fall/glide phases). Joystick input does not require a server round-trip for local camera.

**Gateway:** `battle_flow.Match.handle` applies pose updates. Position uses ClientInterface message **3** — layout **unknown** (RO-057). Do not treat 0xBC/0xBD as position.

**Backlog:** RO-082 (research table per action), RO-083 (`battle/modules/actions.py`).

**JSON simulator:** `app/game/simulate._move` — normalized planar input, one base speed (no sprint/crouch/prone). See `tests/compatibility/gameplay/test_movement.py` (local contract, not original RoS).

Status tracker: [PLAYER_SYSTEM_STATUS.md](PLAYER_SYSTEM_STATUS.md) section 3.
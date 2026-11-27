# Player combat (restoration notes)

**Gateway:** Gun pickup and slot properties exist (`PropsModule`, legacy `Match`). **No** shared authoritative firearm damage or hit validation to match end yet (GAMEPLAY_FUNCTION_AUDIT: Missing).

**JSON simulator:** `simulate._shoot`, gear mitigation in `items.py` — full loop for custom WebSocket clients only.

**Backlog:** RO-085+ combat, RO-084 equip slots, knockdown RO-093.

Status: [PLAYER_SYSTEM_STATUS.md](PLAYER_SYSTEM_STATUS.md) sections 5–6.
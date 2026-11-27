# Door research payloads (RO-074)

Read-only Frida Python payloads. Use **`tools/probe.sh`** in a live map **700** match after `tools/to_match.sh`.

| File | Purpose |
|------|---------|
| `snapshot_opened_elements.py` | Logs player position, `space.openedElements`, and handler names for correlation with gateway `[BATTLE] <- ...openElement` lines. |
| `../pkg_door_probe.py` | Older combined door + inventory probe (same `openedElements` line). |
| `../call_open_element.py` | **Synthetic** wire reproduction (elem 832); not a substitute for UI OPEN acceptance rows. |

Acceptance evidence: gateway log excerpt from **live** `bigworld_gateway/logs/server.log` (archived `server.prev*.log` rows are wire history only) + optional snapshot output pasted into `docs/DOORS_AND_ELEMENTS.md` §8 and `server/extract/map700_elements.json` → `buildings[]`.
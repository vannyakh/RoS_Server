# Solo match fill config (RO-110)

Gateway-local Solo Battle Royale fill settings for the first-playable milestone.
**Not** original Rules of Survival matchmaking. Defaults below are **proposed / unverified** until LDPlayer (or authorized device) evidence updates them.

Related: [GATEWAY_BATTLE_SESSION.md](GATEWAY_BATTLE_SESSION.md) · [SOLO_GAMEPLAY_STATUS.md](../SOLO_GAMEPLAY_STATUS.md) · `bigworld_gateway/docs/BOT_ENTITIES.md` (RO-068).

## Boundary

| Rule | Detail |
| --- | --- |
| Location | `bigworld_gateway/server/battle/data/solo_fill.json` + `battle/modules/solo_fill.py` |
| Seam | `register(session)` on `MatchSession` (RO-058). No new `server/modules/` tree. |
| No `app/` | This module must not import the FastAPI package. |
| No opcodes | Does not invent Mercury messages; sends no createEntity / leaveAoI bytes. |
| Consumers | RO-069 reads `session.solo_fill.bot_count` to spawn Robot entities. |

## Proposed defaults (UNVERIFIED)

| Param | Proposed value | Status |
| --- | --- | --- |
| Humans | 1 | unverified |
| Bots at start | 9 | unverified (scale toward 29 / 59 / 119 later) |
| Warmup | ~30 seconds | unverified |
| Map id | unknown (`null`) | remaining issue |
| Mode id | unknown (`null`) | remaining issue |

## JSON keys (`solo_fill.json`)

| Key | Type | Meaning |
| --- | --- | --- |
| `human_count` | int | Expected human players in the fill (proposed: `1`) |
| `bot_count` | int | Bot slots to fill (`N`; proposed start: `9`) |
| `warmup_seconds` | number | Proposed pre-boarding warm-up length in seconds (`30`) |
| `bot_scale_targets` | int[] | Later scale gates (`[29, 59, 119]`); not auto-applied |
| `map_id` | int or null | Solo map selection; **null until researched** |
| `mode_id` | int or null | Lobby / match mode id; **null until researched** |
| `remaining_issues` | string[] | Open research items (map/mode/warmup provenance) |

Optional env overrides (experiments only; still not original rules): `SOLO_HUMAN_COUNT`, `SOLO_BOT_COUNT`, `SOLO_WARMUP_SECONDS`.

Raising `N` is a **data** change: edit `bot_count` in `solo_fill.json` (or set `SOLO_BOT_COUNT`). No edit to `ros_server.py` is required.

## Module API

```python
def register(session):
    # attaches SoloFillConfig at session.solo_fill
    ...
```

`session.solo_fill` exposes:

- `human_count`, `bot_count`, `warmup_seconds`
- `bot_scale_targets`, `map_id`, `mode_id`, `remaining_issues`
- `alive_num` → `human_count + bot_count` (gateway convention for space HUD; see BOT_ENTITIES.md)

## What this task does not do

- Does not spawn Robot entities (RO-069).
- Does not rewrite `timeline.json` or `space.json` (those stay owned by their tasks; consumers may read `warmup_seconds` / `alive_num`).
- Does not claim original matchmaking, lobby queue rules, or PREPARE_TIME provenance.

## Remaining issues

1. `map_id` for Solo BR selection is unknown until researched (`space.json` mapID 700 is a separate gateway space default).
2. `mode_id` / lobby teamType for Solo matchmaking is unknown until researched.
3. `warmup_seconds` (~30) is a proposed gateway value; original `mapData.PREPARE_TIME` is not traced here.
4. `aliveNum = human_count + bot_count` is a gateway convention for RO-069; not claimed as original fill logic.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/solo_fill -q --tb=line
```

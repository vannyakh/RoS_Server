# Gateway battle MatchSession seam

Owner task: RO-058. Scope: architecture of the original-client gateway match path.
This note does not claim original Rules of Survival protocol compatibility.

## Boundary

`bigworld_gateway/` is a separate process from the FastAPI modular monolith in `app/`.

| Rule | Detail |
| --- | --- |
| No cross-import | `bigworld_gateway/**` must not import `app/`. `app/` must not import `bigworld_gateway/`. |
| Match state | Live match entities, timers, doors, loot, bots, and positions stay **gateway-local** in memory on the MatchSession. |
| Durable results | Only the final match report crosses the process boundary, via `POST /api/v1/gateway/.../matches` (RO-070). The gateway uses HTTP to that route; it never opens the SQLite/Postgres file. |
| JSON simulator | `app/game/` is a separate versioned-JSON match loop. Its countdown, loot table, and bot rules are not wired into the gateway. |

## Why a seam

Before RO-058 the whole battle path lived inline in `bigworld_gateway/server/ros_server.py` (`matchBattleGround`, `_enter_battle`, `trigger_battle.txt`, Athlete decoder gated by `_in_battle`). Later features would all collide on that file.

The seam is `MatchSession`: one instance per client address. Later tasks add a file under `bigworld_gateway/server/battle/modules/` instead of editing `ros_server.py`. The gate keeps only thin hook calls.

## MatchSession

Location: `bigworld_gateway/server/battle/session.py`.

| Concern | API | Notes |
| --- | --- | --- |
| Entity id allocator | `alloc_space_id`, `alloc_plane_id`, `alloc_prop_id`, `alloc_bot_id` | Fixed space/plane; monotonic props and bots |
| Ordered send queue | `enqueue(body)`, `flush()` | FIFO over the gate `_send_bundle` wrapper |
| Timeline | `schedule(delay, callback, *args)` | Uses the asyncio loop, or an injected FakeClock / scheduler in tests |
| Inbound dispatch | `on_inbound(key, handler)`, `dispatch_inbound(msgid, payload)` | Modules register; `None` = not handled (legacy `battle_flow` still runs) |
| Lifecycle | `close()` | Clears queue, handlers, and cancels timers |

`HallMatchSession` in the same module remains the lobby START → `matchBattleGround` → delayed `_enter_battle` owner. It is not the in-match seam.

## Entity id ranges

Gateway defaults (overridable by env for experiments). These are **this project's** stable ids for the gateway client path, not a published original-server allocation table.

| Kind | Default | Env | Allocator |
| --- | --- | --- | --- |
| BattleGroundSpace | `20001` | `SPACE_ENTITY_ID` | `alloc_space_id()` (fixed) |
| Plane | `20002` | `PLANE_ENTITY_ID` | `alloc_plane_id()` (fixed) |
| DtsProp (loot) | `30000+` | `PROP_ENTITY_ID_BASE` | `alloc_prop_id()` |
| Robot / bots | `40000+` | `BOT_ENTITY_ID_BASE` | `alloc_bot_id()` |

Player avatar id stays under the existing gate env (`AVATAR_ID`, default `10003`) and is not allocated by MatchSession.

## Module registration contract

Directory: `bigworld_gateway/server/battle/modules/`.

1. Each feature is one `*.py` file (names not starting with `_`).
2. The file exposes `register(session: MatchSession) -> None`.
3. On `_enter_battle`, the gate creates a `MatchSession` and calls `load_battle_modules(session)`.
4. `register` may call `session.on_inbound(...)`, `session.schedule(...)`, `session.enqueue(...)`, and the id allocators.
5. If the directory is missing or empty, load is a no-op: enter-battle handoff and `trigger_battle.txt` keep working exactly as before.
6. If import or `register` raises, the loader logs the error and continues. The session stays usable.

Example module shape (later tasks own the real files):

```python
def register(session):
    session.on_inbound("openElement", _on_open)

def _on_open(msgid, payload):
    return b""  # or reply bytes; None means fall through to battle_flow
```

Inbound handler return values:

- `None` from `dispatch_inbound` overall → no module matched; `ros_server` keeps the legacy `battle_flow.Match` path.
- `bytes` (including empty) → a module handled the message; do not also run that legacy handler for the same packet.

## Gate hooks (`ros_server.py`)

| Hook | When |
| --- | --- |
| `_start_match_session(addr)` | End of `_enter_battle` after avatar create messages; sets `session.gate` and `session.bf_key` for modules (RO-071 lobby return) |
| `_match_session(addr)` | Lookup |
| `_end_match_session(addr)` | Player leaves the match (Quit Game / leave flag) |
| `dispatch_inbound` before `battle_flow.Match.handle` | Only uses the reply when a module handled the message |

`battle/modules/results.py` calls `apply_lobby_return(gate, addr, bf_key)` after the result delay when `session.gate` is set (same path as Quit Game → Athlete).

`trigger_battle.txt` and the pre-start space / flight paths still call `battle_flow` and `_send_bundle` directly so behaviour is unchanged with zero modules.

## Follow-on tasks

Modules and encoders land in later RO-059+ tasks (`battle/modules/space.py`, plane, props, bots, requests decoder, match report). This seam does not implement gameplay.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/compatibility/gateway/session -q --tb=line
```

Search under `bigworld_gateway/server` must find no `from app` / `import app`.

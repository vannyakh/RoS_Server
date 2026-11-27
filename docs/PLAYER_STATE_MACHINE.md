# Player state machine (gateway runtime)

Authoritative **gateway-local** lifecycles in `battle/player_entity.py`. These strings are for engineering tracking, not original client enum ids.

## Match lifecycle (`PlayerRuntimeState.lifecycle`)

```text
MATCH_LOADING → PREPARATION → AIRCRAFT → PARACHUTE → GROUND
                                              ↓
                                         VEHICLE (optional)
                                              ↓
                    ELIMINATED / SPECTATOR → RESULTS → (session teardown → hall)
```

| State | Set by | Notes |
| --- | --- | --- |
| `MATCH_LOADING` | `MatchSession` / `player_runtime` start | Battle inventory cleared |
| `PREPARATION` | Timeline `boarding` | Prep island countdown |
| `AIRCRAFT` | Timeline `flight` | Plane module |
| `PARACHUTE` | Jump module off-plane | Until land |
| `GROUND` | Jump `_land` or timeline `play` | Gameplay |
| `VEHICLE` | Future RO-091 | Driver/passenger |
| `ELIMINATED` | `set_eliminated()` | Solo: no revive |
| `SPECTATOR` | Future | If client supports |
| `RESULTS` | `results_module` | Before lobby return |

## Action gates

- `can_perform_combat_action()` is false when eliminated, disconnected, healing, or in `RESULTS`/`SPECTATOR`.
- Firing after elimination must be rejected once combat module (RO-085+) reads this flag.

## Stance & movement (planned RO-083)

| Field | Values |
| --- | --- |
| `stance` | `STANDING`, `CROUCH`, `PRONE` |
| `movement_state` | `IDLE`, `WALK`, `SPRINT`, `SWIM` |
| `action_state` | `NONE`, `FIRE`, `RELOAD`, `HEAL`, `INTERACT` |

## JSON simulator (`app/game`)

Separate states: `roaming`, `queued`, `countdown`, onboard/dropping/playing via match phase. See `app/game/state.py` and `docs/GAMEPLAY_FUNCTION_AUDIT.md`.
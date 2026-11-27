# Player protocol mapping (gateway path)

Maps **player-facing behaviors** to evidenced Mercury / entity methods. Not an official RoS opcode list.

| Player function | Client → server (evidenced) | Server → client | Task |
| --- | --- | --- | --- |
| Lobby START handoff | Athlete `createHallTeam`, `matchBattleGround` | `onEnterHallTeam`, `syncMatchState` | RO-107/108 |
| Enter battle | Account handshake | `resetEntities`, `createBasePlayer` BattleGroundAvatar | RO-056 |
| Space / countdown | — | `createEntity` BattleGroundSpace, property stream | RO-061 |
| Plane | — | Plane entity, `inJumpArea` | RO-062 |
| Jump / parachute | Avatar `requestGetOffPlane`, `chooseParachute`, `chooseGlider` | Property updates, `forcedPosition` 0x59 | RO-063 |
| Pose (stand/crouch/prone) | Avatar `changePose` | `pose` property update | Legacy `battle_flow.Match` |
| Fall / glide phases | `fall`, `changeFallPhase`, `changeGlidePhase` | `fallPhase`, `glidePhase` | Legacy + jump module |
| Position (unknown layout) | ClientInterface msg **3** (not 0xBC/0xBD) | — | RO-057 |
| Lean | `syncLeanState` | — | RO-082 |
| Generic actions | `doCommonGameAction`, `doInGameAction` | `onOwnDoInGameAction` | RO-082/083 |
| Loot pickup | DtsProp `tryPickUp` | `onAddDtsItem`, `onWearDtsWeapon`, `leave_aoi` | RO-066/077 |
| Doors | Space `openElement`, `closeElement` | `onElementOpen`, `onElementClose` | Legacy Match |
| Safe zone | — | Circle properties, `isInPoisonArea`, hp updates | RO-064 |
| Match end | `requestLeaveSpaceBeforeWin`, `suicideFromClient` | `gameEnd`, `onBattleGroundResult` | RO-071 |

Persistent profile (nickname, currency, depot) uses HTTP **`/api/v1/gateway`** from the gateway — not battle Mercury.

See also: [PROTOCOL_MAPPING.md](PROTOCOL_MAPPING.md), `bigworld_gateway/docs/LOBBY_FINDINGS.md`.
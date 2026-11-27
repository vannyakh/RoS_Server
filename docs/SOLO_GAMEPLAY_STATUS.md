# Solo Battle Royale gameplay status

**Authority:** CTO plan tracker. **Not** original-server proof.  
**Generated:** 2026-11-26. Params below are **proposed** (NOT_CHECKED against original APK).

Statuses: `NOT_CHECKED` | `MISSING` | `BROKEN` | `PARTIAL` | `IMPLEMENTED` | `VERIFIED` | `BLOCKED`.

Related: [RESTORATION_STATUS.md](RESTORATION_STATUS.md) · Phase 09 tasks in `.cursor/management/tasks.json` · [GATEWAY_BATTLE_SESSION.md](engineering/GATEWAY_BATTLE_SESSION.md).

## First playable milestone

**Goal:** Lobby Solo Start → enter match → see 9 bots → aircraft → parachute → land (LDPlayer + original APK + `bigworld_gateway/`).

| Gate | Status | Tasks | Notes |
| --- | --- | --- | --- |
| Lobby START → battle handoff | IMPLEMENTED | RO-107, RO-108 | Mobile evidence recorded; re-verify as needed |
| createEntity framing | DOCUMENTED | RO-056 | Research evidence; not original-compatible |
| MatchSession seam | IMPLEMENTED | RO-058 | Gateway-local; no `app/` import |
| Entity encoders (space/plane/prop) | IMPLEMENTED | RO-059 | Completed: wire 12 passed; live AC4 specialist+QA log spot-check; not VERIFIED original |
| C2S in-match request ids | DOCUMENTED | RO-057 | Completed: OPEN 0x88 / pickup 0x81; 0xBC/0xBD = Avatar methods not position |
| In-battle C2S decoder | IMPLEMENTED | RO-060 | Completed (QA+security): 15 tests; not wired to ros_server; AC4 deferred; msg3 position unknown |
| Space + countdown | IMPLEMENTED | RO-061 | Completed (QA pass-with-AC4-open): aliveNum=100 live; countdown photo + BATTLE_SPACE=off open |
| Plane + boarding | IMPLEMENTED | RO-062 | Completed (QA pass-with-AC4-open); live AC4 still open |
| Jump / parachute / land | IMPLEMENTED | RO-063 | Completed (QA pass-with-AC4-open); live AC4 still open |
| Bot entity research | DOCUMENTED | RO-068 | Completed: Robot entity research (pytest/docs); combat deferred |
| Solo fill 1+N bots | IMPLEMENTED | RO-110 | Completed: `solo_fill` module; N=9 default (**unverified** on LDPlayer) |
| 9 bots visible in match | IMPLEMENTED | RO-069 | **Review:** `battle/modules/bots.py`; LDPlayer visibility → RO-113 |
| First-playable LDPlayer accept | BROKEN | RO-113 | **2026-11-27:** Hall reached (screenshot + `athleteEnterHall` keypoint); still **0** `createHallTeam`/`matchBattleGround`/battle `resetEntities`. START UI visible; bots/plane/land NOT_RUN. Owner: RO-107/108 until markers pass. Evidence: `docs/testing/solo_first_playable.md`. Not original-compatible. |

## Proposed solo config (NOT verified)

| Param | Proposal | Status |
| --- | --- | --- |
| Mode | Solo | NOT_CHECKED |
| Map | ghillie / fiord (proposal) | NOT_CHECKED |
| Humans | 1 | NOT_CHECKED |
| Bots at start | 9 (scale 29 / 59 / 119 later) | NOT_CHECKED |
| Warmup | ~30s | NOT_CHECKED |
| Match length target | ~25 min | NOT_CHECKED |
| Bot AI | FSM / behavior tree / nav — **not** LLM | NOT_CHECKED |
| Fairness | No teleport, wallhack, or omniscience | NOT_CHECKED |

## Architecture mapping (target → existing)

| User sketch | Existing home | Do not |
| --- | --- | --- |
| Matchmaking / fill | `bigworld_gateway/server/battle/` + hall START (RO-107) | Invent `server/modules/` tree |
| Battle session | `battle/session.py` MatchSession (RO-058) | Import `app/` from gateway |
| Wire encoders | `battle_flow.py` then modules (RO-059+) | Invent opcodes without capture |
| Space / plane / jump / bots | `battle/modules/*.py` (RO-061+) | Parallel monolith under `app/game` for APK |
| Results to RoS_Server | `/api/v1/gateway` (RO-070) | Open SQLite from gateway |

## Ordered wave (first playable)

1. Handoff done (RO-107/108) + framing/seam (RO-056/058)
2. RO-059 entity encoders
3. RO-057 C2S ids (parallel with game-compat)
4. RO-061 space + countdown
5. RO-062 plane
6. RO-063 parachute/land
7. RO-068 bot research → RO-069 + RO-110 fill (9 visible)
8. RO-113 LDPlayer acceptance

Post-playable: loot/doors/combat/zone/vehicles/knockdown (RO-064–094), scale gates (RO-112), bot AI engine (RO-111).

## Explicit blockers

| Blocker | Why it matters |
| --- | --- |
| Protocol / property stream | Wrong createEntity framing breaks all non-player entities |
| Entity sync / AoI | Duplicate createEntity without leaveAoI causes RESEND |
| Collision / navmesh data | Bot locomotion and fair combat need map collision; source unknown until researched |
| C2S cell method ids | Without RO-057, jump/pickup/openElement decoding stays raw |

## Rules

- Do not mark a row `VERIFIED` without LDPlayer (or authorized device) logs/screenshots.
- Do not mark original-client `compatible` without an authorized reference and a reviewed task.
- Do not invent Mercury opcodes or a second gateway tree.

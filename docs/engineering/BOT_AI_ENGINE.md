# Bot AI engine design (RO-111)

Gateway-local, non-LLM AI for Solo BR Robot bots on the original-client path.
**Not** original Rules of Survival bot logic. **Not** an original-compatible claim.
Wire sync stays limited to RO-068 evidence; this document invents **no** Mercury opcodes
and **no** Robot property layouts beyond what `bigworld_gateway/docs/BOT_ENTITIES.md` already records.

Related: [GATEWAY_BATTLE_SESSION.md](GATEWAY_BATTLE_SESSION.md) · [SOLO_MATCH_FILL.md](SOLO_MATCH_FILL.md) ·
[SOLO_GAMEPLAY_STATUS.md](../SOLO_GAMEPLAY_STATUS.md) · `bigworld_gateway/docs/BOT_ENTITIES.md` (RO-068) ·
`bigworld_gateway/server/battle/modules/bots.py` (RO-069).

Machine-readable summary: `bigworld_gateway/server/battle/data/bot_ai_notes.json`.

---

## 1. Design choice: hierarchical FSM

**Choice: hierarchical finite-state machine (HFSM), not a behavior tree, not an LLM.**

| Option | Verdict |
| --- | --- |
| **HFSM (chosen)** | One active ground mode per bot; transition guards encode fairness and priority. Fits `MatchSession.schedule` without a BT runtime. Easy to audit (no teleport / no omniscience) at every transition. |
| Full behavior tree | Deferred. A selector tree can wrap the same modes later if RO-112 scale needs composable subtrees; not required for first AI. |
| LLM / remote model | **Forbidden.** No tokens, no prompts, no external inference in the match loop. |

Rationale vs BT: current gateway bots are static create-only (RO-069). The next implementable step is discrete modes with perception guards, not a parallel BT library. Priority among loot / move / engage / flee is expressed as **ordered transition rules** (section 4), which is the FSM equivalent of a BT selector.

`app/game` JSON-simulator bots (if any) stay separate. Gateway AI must not import `app/`.

---

## 2. Module mapping (existing tree only)

Do **not** invent a parallel `server/modules/` tree. Own AI under the existing battle seam:

| Piece | Home | Role |
| --- | --- | --- |
| Spawn / leaveAoI / aliveNum | `battle/modules/bots.py` (RO-069) | Robot type **58** create; ids `40000+`; static pose today |
| Fill N | `battle/modules/solo_fill.py` + `battle/data/solo_fill.json` (RO-110) | `bot_count` default 9; scale targets later (RO-112) |
| AI tick / modes | **Future** `battle/modules/bot_ai.py` (or extend `bots.py` under a later task) | Owns HFSM state, perception queries, intent |
| Proposed AI params | `battle/data/bot_ai_notes.json` (this task) | Perception / speed placeholders; `remaining_issues` |
| Match seam | `battle/session.py` (RO-058) | In-memory positions, `schedule`, `enqueue` |
| Wire encoders | `battle_flow.py` + RO-059 helpers | Only documented messages |

Boundary rules:

1. AI updates **gateway-local** intent and (when allowed) in-memory transform.
2. AI never opens the database and never imports `app/`.
3. AI never invents `detailedPosition` (**0x58**) bytes. Continuous walk sync is **blocked** until a capture documents the layout (RO-068 remaining_issues).
4. `forcedPosition` (**0x59**) is a **candidate** sparse relocate only; live-tested for own avatar, **not** for Robot (RO-068). Do not use it as a walk substitute or as unfair teleport.
5. Scale 9 → 29 → 59 → 119 is **RO-112**; this design assumes N=9 first.

---

## 3. Top-level states (HFSM)

Each bot holds one **mode**. Modes below cover the acceptance set: loot, move, engage, flee.
Airborne / prep modes are stubs until plane/jump bot participation is researched.

| State | Purpose | Typical actions (intent only) |
| --- | --- | --- |
| `IDLE` | Default after spawn / between goals | Face random yaw; no move until move sync is allowed |
| `MOVE` | Path toward a waypoint (POI, loot, cover, zone) | Set move intent along a fair path; stop at goal radius |
| `LOOT` | Acquire visible ground gear | Move to sensed DtsProp; pickup when in reach (needs RO-064/loot C2S wiring) |
| `ENGAGE` | Fight a **perceived** hostile | Aim / fire / strafe only against targets that pass perception + LOS |
| `FLEE` | Break contact when disadvantaged | Move away from last-known threat; prefer cover / safer circle |
| `DISABLED` | Dead / match end / leaveAoI | No AI; RO-069 already leaveAoI on session close |

Optional later sub-states (not required for RO-111 design acceptance): `RELOAD`, `HEAL`, `ZONE_ESCAPE`, `AIRCRAFT`, `PARACHUTE`. They must still use the same fairness rules.

### 3.1 State ↔ behavior summary

| Behavior | Primary state | Notes |
| --- | --- | --- |
| Loot | `LOOT` (enter from `MOVE`/`IDLE`) | Only items inside perception; no global loot table omniscience |
| Move | `MOVE` | Speed-capped; collision-respecting when nav exists; no teleport |
| Engage | `ENGAGE` | Requires sensed target + LOS; no wallhack aim |
| Flee | `FLEE` | Triggered by low HP vs armed threat, or unarmed + threat in sense range |

---

## 4. Decision priority (transition order)

On each AI tick, evaluate **first match wins** (selector-equivalent):

1. `DISABLED` if dead / session closing.
2. `FLEE` if a sensed armed threat exists and (HP below flee threshold **or** bot has no usable weapon).
3. `ENGAGE` if a sensed hostile is in FOV+range **and** LOS is proven **and** bot has a usable weapon.
4. `LOOT` if poorly geared and a sensed loot entity is within loot sense range.
5. `MOVE` toward next waypoint (zone-safe POI, last-known contact, or roam).
6. Else `IDLE`.

Until continuous position sync is documented, modes may run **internally** for tests, but **must not** emit invented walk packets to the client. Static RO-069 spawn remains the safe live default.

---

## 5. Fair perception (mandatory)

Bots are **not** omniscient. Perception is a query the AI may ask; world state the server knows for adjudication is separate from what a bot “knows.”

### 5.1 Proposed senses (UNVERIFIED placeholders)

Values live in `bot_ai_notes.json`. They are **gateway proposals**, not original RoS numbers.

| Sense | Proposal | Meaning |
| --- | --- | --- |
| Sight range | `120` m | Max distance for visual acquire of hostiles / loot |
| Sight FOV | `110` deg | Horizontal cone around bot yaw |
| Hearing range | `40` m | Gunfire / footsteps cue → last-known position only (no exact wall pierce) |
| Loot sense range | `35` m | Ground items the bot may path to |
| Engage range cap | `min(sight, weapon)` | Cannot shoot beyond sense or beyond local weapon rule |
| Memory TTL | `8` s | Last-known position expires; no permanent tracker |

### 5.2 Line of sight (LOS)

- Engage and precise aim require **LOS** through collision / blocker data.
- **Fail closed:** if collision/navmesh source is unknown, `ENGAGE` stays **disabled** (bots must not shoot “through” unknown geometry). That is how wallhack is forbidden before nav exists.
- Hearing may set a last-known XY without granting current accurate position behind cover.

### 5.3 Forbidden behaviors

| Forbidden | Rule |
| --- | --- |
| Teleport | No instant position jumps for chase/loot/cover. No leaveAoI+recreate as movement. No abuse of `forcedPosition` as a walk hack. |
| Wallhack | No aiming or pathing that ignores solid blockers once nav exists; until then, no engage. |
| Omniscience | No reading full match player list, full loot table, or exact HP of unsensed targets. |
| LLM | No language-model decisions in the tick. |
| Invented opcodes | No fabricated `0x58` layouts or undocumented Robot method ids. Cite RO-068 only. |

Server-authoritative hit validation (when combat is implemented) may use true positions; that is **not** bot perception.

---

## 6. Movement, nav, and collision

### 6.1 Known (RO-068 / RO-069)

| Fact | Source |
| --- | --- |
| Robot client type **58**; create via enterAoI + createEntity | BOT_ENTITIES.md |
| Initial pose = createEntity header position + packed yaw | RO-056 / RO-068 sample |
| Volatile position/yaw declared on `robot.def` | RO-068 |
| Continuous walk via **detailedPosition (0x58)** layout | **Unknown** — do not invent |
| **forcedPosition (0x59)** layout | Captured for **own avatar**; Robot unproven |
| Static N bots from `solo_fill.bot_count`; leaveAoI on end | RO-069 `bots.py` |
| Prep placement = seeded grid near anchor | `place_bots` in `bots.py` |

### 6.2 Nav / collision data sources

| Source | Status |
| --- | --- |
| Gateway `battle/data/*.json` | Spawn/fill/timeline/space only — **no** navmesh |
| Client map / NeoX scene collision | **Unknown** for server use; proprietary assets must not be committed |
| Extracted navmesh / blocker mesh in-repo | **Not present** |
| `app/game` blocker index (JSON simulator) | Separate process; **not** wired to gateway; must not be imported |

**remaining_issues (nav):**

1. Name or produce a **gateway-legal** collision/nav source (authored JSON blockers, researched extract, or deferred).
2. Until that source exists, locomotion AI may only use open-field assumptions for **offline** planning tests; live client move sync stays static.
3. Height / building floors / water rules are unknown.

### 6.3 Combat rules (when unblocked)

- Same speed and gravity assumptions as humans once movement sync exists (local gateway rules, not original stats).
- Fire only at perceived + LOS targets within engage cap.
- No snap-aim through walls; no instant turn beyond a max yaw rate (placeholder in JSON).
- Death / kill-feed / `dtsKillTip` remain research-gated (RO-068 §4–6); do not invent method payloads here.

---

## 7. Implementation phases (recommendation to CTO)

| Phase | Work | Gate |
| --- | --- | --- |
| A (this task) | Design + `bot_ai_notes.json` | Docs only |
| B | In-memory HFSM on MatchSession for N=9; still **no** walk packets | After RO-113 visibility confidence optional |
| C | Continuous move sync | Only after **0x58** (or proven Robot `0x59`) capture — new research/protocol task |
| D | Fair engage / flee with LOS | After nav/collision source named and wired |
| E | Scale 29/59/119 | RO-112 performance gates |

---

## 8. Compatibility and evidence discipline

| Field | Value |
| --- | --- |
| implementation_status | design_only (RO-111) |
| compatibility_status | unknown |
| original_reference | none claimed; RO-068 client `.def` + gateway captures only |
| opcodes invented | **none** |

Cite RO-068 for entity type, create props, and movement unknowns. Do not treat message-map names as layouts.

---

## 9. remaining_issues

1. Live Robot createEntity accept on LDPlayer (RO-068 / RO-113).
2. `detailedPosition` (**0x58**) 30-byte layout for Robot — unknown.
3. Robot `forcedPosition` (**0x59**) behavior — unproven.
4. Collision / navmesh data source for fair LOS and pathing — unknown.
5. Loot entity sensing depends on DtsProp spawn + pickup research (RO-064+).
6. Combat S2C (`damage` / `die` / `dtsKillTip`) formats — unknown; skip until researched.
7. Bot plane boarding / parachute AI — out of first HFSM ground scope.
8. Whether original bots use Robot 58 only or variants — out of scope (stay on 58).

# Map 700 doors and scene elements (RO-074)

`compatibility_status`: **unknown** (research). Local gateway echoes are **not** original-server proof.

Build: Rules of Survival `1.610637.617289`. Map: **700** (4K battleground).

Machine-readable rows: `server/extract/map700_elements.json`. Wire ids: `docs/BATTLE_CLIENT_REQUESTS.md` section 2.

---

## 1. Contract (from `.def` + live capture)

Doors are **not** separate entities. They are **interact elements** on the space entity (`Globals.spaceEntity`, type `BattleGroundSpace`).

| Direction | Name | Signature | Notes |
|-----------|------|-----------|--------|
| Client → server (cell, exposed) | `openElement` | `INT32 elemID`, `INT8 state` | Msg **`0x88`**, var16, target **space entity id** (gateway default **20001**) |
| Client → server (cell, exposed) | `closeElement` | `INT32 elemID` | Msg **`0x89`** |
| Server → client | `onElementOpen` | `INT32 elemID`, `INT8 state` | Client method **40** of 66 (raw `.def` index; Space uses CM offset **0**) |
| Server → client | `onElementClose` | `INT32 elemID` | Client method **41** of 66 |
| Property (ALL_CLIENTS) | `openedElements` | `ARRAY<DTS_ELEMENT>` | `DTS_ELEMENT = { elemID INT32, state INT8 }`; property index **67** on `createEntity` for BattleGroundSpace |

**Captured open (verified on wire):**

```text
880900214e00004003000001
→ [BATTLE] <- BattleGroundSpace(20001).openElement args=4003000001
→ elemID 832, state 1
```

Source: `client/frida/payloads/requests/open_element_832.hex.txt`, `server/extract/battle_cell_exposed.json` → `_captures.BattleGroundSpace.openElement`.

**Captured close (same elem):** `890800214e000040030000` (elem **832**, no state byte).

---

## 2. Gateway behavior today (`battle_flow.py`)

When `_in_battle` and `decode_request` routes to `Match.handle`:

1. **`openElement`**: unpack `elem` (i32) + `state` (i8); store `Match.doors[elem] = state`; reply `client_call("BattleGroundSpace", "onElementOpen", SPACE_ID, args[:5])` (echo bytes).
2. **`closeElement`**: unpack `elem`; store `Match.doors[elem] = 0`; reply `onElementClose` with `args[:4]`.

**Not implemented on the gateway:**

- No `openedElements` property update (`prop_update` on index 67).
- No `openedElements` seeding in the space `createEntity` blob beyond client defaults.
- No pairing logic for double doors.

Evidence: `grep openedElements bigworld_gateway/server/*.py` → no writers; `LOBBY_FINDINGS.md` update 10: "meaning of `state` and the `openedElements` property are **not used yet**".

---

## 3. Client-side behavior (Frida / logs, unverified against official server)

From `LOBBY_FINDINGS.md` **update 11**:

- `BattleGroundSpace.onElementOpen` / `onElementClose` **look up a scene object** and call `ChangeInteractModelState(OPEN/CLOSED)`.
- Replies for **832** (`openElement(832,1)`, `closeElement(832)`) caused **no client script errors**.
- A **visible** door animation was **not** captured in a screenshot.

From **update 13**: one UI OPEN press produced **no** `openElement` line in the gateway log (possible client freeze; **cause not resolved**).

Read-only probe sketch: `client/frida/payloads/pkg_door_probe.py` (logs `space.openedElements` and bytecode names for `onElementOpen`, `set_openedElements`, `openedElementsUpdate`).

---

## 4. `openedElements` — is it required?

| Question | Status | Evidence |
|----------|--------|----------|
| Must the server **mirror** each open into `openedElements`? | **Unverified** | `CREATE_ENTITY_FORMAT.md` §7 says remove entry on close and include on createEntity for late joiners; no live test |
| Does **only** `onElementOpen` suffice for the local presser? | **Partial** | Update 11: echo works without property update for 832, no errors; visibility unknown |
| Late join / space recreate | **Missing** | Gap review row **(1b)**: property never written; `LOBBY_FINDINGS` "no door state replay" |
| Initial space create | **Unverified** | Index 67 documented; gateway `space` / `spacet` commands — confirm whether default mask omits `openedElements` |

**Working hypothesis for RO-075 / RO-067** (not proof): treat **`onElementOpen`/`onElementClose` echo** as the minimum reply for the acting client; add **`openedElements`** updates when RO-056 property encoder is used for ALL_CLIENTS fields, and when join-replay tests fail without them.

---

## 5. INT8 `state` meanings

| Value | Seen on wire? | Gateway behavior | Meaning |
|-------|---------------|------------------|---------|
| **1** | Yes (most logged opens: **815–818**, **831–834**, **836**, **832**) | Echoed on `onElementOpen` | **Unverified** — likely open direction / leaf index; not in `.def` text |
| **2** | Yes (`openElement` for elem **832**, `server.prev5.log`) | Echoed (assumed) | **Unverified** — may be second leaf or alternate open pose |
| **3** | Yes (`openElement` for elem **4660**, `server.prev4.log`) | Echoed with state **3** | **Unverified** — paired with `closeElement` on elem **4661** in same recv bundle (double-door hypothesis) |
| **0** | Not captured on open | `Match.doors[elem]=0` on close | Close path uses `closeElement`, not `openElement(…,0)` |
| **4+** | Not captured | — | **Unknown** |

**Unverified:** whether the OPEN button label or animation differs per `state` value.

---

## 6. Double doors

| Question | Status |
|----------|--------|
| One or two `elemID`s per doorway? | **Unknown** — no paired capture in repo |
| Must both leaves get `onElementOpen`? | **Unknown** |
| Same `state` on both? | **Unknown** |

**Table column** `pair_elem_ids` reserved in `map700_elements.json` for RO-075.

---

## 7. Out of scope (per task)

These use **other** APIs, not `BattleGroundSpace.openElement`:

- **Vehicle doors**: `IVehicle.openDoor` / `closeDoor`, `onOpenDoor` / `onCloseDoor`, `doorOpened`.
- **Elevator / dungeon**: `ElevatorCage`, `DungeonSpace` `openDoor`.
- **Sliding / garage** on map 700: **unverified** — no `openElement` capture; may still use space element ids once logged.

---

## 8. Building table template (fill during `tools/to_match.sh` runs)

**Live AC4 pass (2026-11-27, game-compatibility-engineer):** `grep` on `bigworld_gateway/logs/server.log` for `openElement`, `closeElement`, and `onElementOpen` returned **no lines** (current log is a fresh session). Archived gateway logs under `bigworld_gateway/logs/server.before-*.log` and `server.prev*.log` contain the wire evidence below. **LDPlayer / `to_match.sh` was not driven from the agent environment** — placeholder rows remain for a labeled third building, visible-motion confirmation, and a fresh failure capture. Outbound `onElementOpen` is **not** printed in any log file (gateway only logs inbound `[BATTLE] <-`).

One **row per building / doorway tried** on map 700. Copy the block below for each site.

### Template

| Field | Record here |
|-------|-------------|
| Building (landmark / minimap) | e.g. "Red warehouse NE" — **required for acceptance** |
| `elemID` | From `[BATTLE] <- BattleGroundSpace(...).openElement` log |
| Client `state` values tried | Comma-separated INT8 from same log |
| Scene object exists? | Frida: `onElementOpen` lookup / no traceback — **unverified until run** |
| Gateway reply tried | e.g. `onElementOpen(echo)` only / + future `openedElements` |
| `openedElements` before/after | `doors/snapshot_opened_elements.py` output |
| Visible result | `opened` / `closed` / `no change` / `no OPEN button` |
| Failure cause | From §9 or `unknown` |
| Log / hex evidence | Gateway line + `client/frida/payloads/requests/*.hex.txt` if saved |

### Observed rows (wire evidence from archived gateway logs)

Building **landmark names** are still **unknown** for all rows below (AC4 requires minimap labels).

| Building (landmark) | elemID | state (C2S) | Close logged? | Gateway log line (representative) | Reply tried | Visible result | Client errors | pair_elem_ids | Notes |
|---------------------|--------|-------------|---------------|-----------------------------------|-------------|----------------|---------------|---------------|-------|
| unknown | 832 | 1, **2** | yes | `[BATTLE] <- BattleGroundSpace(20001).openElement args=4003000001` / `4003000002`; `closeElement args=40030000` | echo open/close | **unknown** | none reported | — | `server.before-flight.log`, `server.prev5.log`; hex sample `open_element_832.hex.txt` |
| unknown | 815 | 1 | no | `openElement args=2f03000001` | echo (assumed) | **unknown** | — | — | `server.before-flight.log` |
| unknown | 817 | 1 | no | `openElement args=3103000001` | echo (assumed) | **unknown** | — | — | `server.before-flight.log` |
| unknown | 818 | 1 | no | `openElement args=3203000001` | echo (assumed) | **unknown** | — | — | `server.before-flight.log` |
| unknown | 831 | 1 | yes | `openElement args=3f03000001`; `closeElement args=3f030000` | echo open/close | **unknown** | — | — | `server.before-spin-restart.log` |
| unknown | 833 | 1 | no | `openElement args=4103000001` | echo (assumed) | **unknown** | — | — | `server.before-spin-restart.log`, `server.prev4.log` |
| unknown | 834 | 1 | no | `openElement args=4203000001` | echo (assumed) | **unknown** | — | — | `server.before-flight.log`, `server.prev4.log` |
| unknown | 836 | 1 | no | `openElement args=4403000001` | echo (assumed) | **unknown** | — | — | `server.before-flight.log` |
| unknown (**double-door candidate**) | **4660** | **3** | yes (on **4661**) | same recv: `openElement args=3412000003` then `closeElement args=35120000` | echo both | **unknown** | — | **4661** | `server.prev4.log` — two elemIDs in one client bundle |

Machine-readable mirror: `server/extract/map700_elements.json` → `buildings[]`.

### AC4 placeholders (complete on LDPlayer specialist run)

| Building (landmark) | elemID | state (C2S) | Visible result | Failure cause | Procedure step |
|---------------------|--------|-------------|----------------|---------------|------------------|
| **AC4_PENDING** — third labeled building | *(fill)* | *(fill)* | *(fill)* | — | `to_match.sh` → land → OPEN/CLOSE → copy line from **live** `server.log` |
| **AC4_PENDING** — failure site | *(fill or none)* | — | `no change` / `no OPEN button` | §9 symptom **A** or **B** | Reproduce owner failure; attach logcat + gateway tail |

**Specialist procedure when automating LDPlayer is available:**

1. Start gateway; truncate or note offset of `bigworld_gateway/logs/server.log`.
2. `bigworld_gateway/tools/to_match.sh` → map **700**, parachute, visit **≥3** distinct buildings (name each from minimap).
3. At each doorway: OPEN then CLOSE; confirm `[BATTLE] <- BattleGroundSpace(20001).openElement` / `closeElement` in **that** `server.log`.
4. Find one **double door**; log whether the client sends one or two `elemID`s (see row **4660/4661** hypothesis).
5. Find one **failure** (no log line or no motion); note symptom from §9.
6. Optional: `tools/probe.sh client/frida/payloads/doors/snapshot_opened_elements.py` after each building.
7. Merge rows into this table and `map700_elements.json` → `buildings[]`; remove `AC4_PENDING` placeholders.

**Failures still open:** owner reports some/all buildings fail; causes in §9 not narrowed per landmark.

---

## 9. Failure modes (gap review + findings)

| # | Symptom | Candidate cause | Checked? |
|---|---------|-----------------|----------|
| A | No `openElement` in log | Client stuck; non-space door path; prompt without cell call | Partial (one event, update 13) |
| B | Logged open, no motion | Bad `elemID` for scene; missing `openedElements`; wrong `state`; double leaf | **No** |
| C | Worked once, not for joiner | `openedElements` / createEntity replay | **No** (gateway gap 1b) |
| D | Outbound reply wrong shape | Server→client `0x80\|idx` for Space methods not byte-captured | **No** (`CREATE_ENTITY_FRAMING.md`) |

---

## 10. Live capture procedure (specialist)

Acceptance criterion: **≥3 buildings**, **one double door**, **one failure**, with logs.

1. `tools/to_match.sh` → map **700**, land, reach buildings on foot.
2. Each OPEN/CLOSE: save gateway lines  
   `[BATTLE] <- BattleGroundSpace.openElement` / `closeElement`.
3. Optional Frida (after game up, `frida-server` **not** at launch):  
   `tools/probe.sh client/frida/payloads/doors/snapshot_opened_elements.py`
4. Merge rows into §8 and append objects to `server/extract/map700_elements.json` → `buildings[]`.
5. For double doors: log **both** elemIDs if the client sends two opens or one open with two states.

**Do not** use `call_open_element.py` for building acceptance rows (synthetic); use it only to reproduce wire format.

---

## 11. Open questions (for RO-075 / RO-067 / live test)

1. Map **700**: complete **elemID → building** table from UI OPEN presses (not just 832).
2. Does the client require **`openedElements`** for the **local** player to see motion, or only for **others** / reconnect?
3. Full set of **`state`** values per door type (sliding vs hinged).
4. **Double-door** pairing rules (one vs two ids; one vs two replies).
5. Outbound **`onElementOpen`** byte capture vs inbound `0x88` (RO-059).
6. Which map 700 interactables **never** call `openElement` (garage, vault glass, etc.).
7. Does failed lookup in `onElementOpen` throw a traceback naming **`elemID`**? (use `pkg_door_probe.py` / live logcat)

---

## 12. Related tasks

| Task | Role |
|------|------|
| **RO-074** | This research |
| **RO-075** | `server/battle/data/doors.json` + coverage tests |
| **RO-067** | `modules/doors.py` loads table (not edited in RO-074) |
| **RO-057** | Request id map (`BATTLE_CLIENT_REQUESTS.md`) |

---

## 13. Extract JSON references

From `server/extract/battle_cell_exposed.json` (`_captures`):

```json
"BattleGroundSpace.openElement": {
  "msgid": 136,
  "full_hex": "880900214e00004003000001",
  "eid": 20001,
  "args_hex": "4003000001",
  "note": "OPEN door press / Frida call_open_element style; elemID=832 state=1"
}
```

From `map700_elements.json` → `observations[0]` (same elem, structured fields for tooling).
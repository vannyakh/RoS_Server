# In-match client → server request ids (RO-057)

Evidence-only map of exposed **cell** method ids used while `_in_battle` is set. Companion extract: `server/extract/battle_cell_exposed.json`. Frida dump script: `client/frida/dump_cell_methods.js`. Hex samples: `client/frida/payloads/requests/`.

`compatibility_status`: **researching / unknown**. Local gateway decode is not original-server proof.

Build: Rules of Survival `1.610637.617289`.

---

## 1. Framing (all entities)

| Field | Value | Evidence |
|-------|--------|----------|
| Message id | `0x80 \| k` for direct indices; extended form when `k >= eff` | Live Space/DtsProp captures; `battle_flow.decode_request`; `ros_server._BASEAPP_EXT_MSGS` |
| Length | **var16** (little-endian u16 after the msgid byte) | Same |
| Payload | `entity_id` u32 LE + optional **sub byte** + argument bytes | Captures below |
| `eff` | `62 - (exposed_count + 192) // 255` | Matches Athlete/entity extended scheme; Avatar `eff=60`, Space/DtsProp `eff=62` |

Extended form (Avatar long table): msgid = `0x80 \| (eff + (k >> 8))`, first payload byte after eid is `k & 0xff`.

---

## 2. OPEN button → which entity and method

When the player presses **OPEN** on a door/element, the client calls:

**`BattleGroundSpace.openElement(INT32 elemID, INT8 state)`** on `Globals.spaceEntity` (gateway space entity id **20001**).

| Item | Value |
|------|--------|
| Exposed index | **8** (of 14 on BattleGroundSpace) |
| Message id | **`0x88`** |
| Sub byte | none (direct) |
| Length width | var16 |
| Arg types | `INT32`, `INT8` |

### Captured hex (door 832, state 1)

Source: `logs/server.prev5.log` cleartext client msgs. File: `client/frida/payloads/requests/open_element_832.hex.txt`.

```text
880900214e00004003000001
```

Breakdown: `88` | len `0900` | eid `214e0000` (20001) | elem `40030000` (832) | state `01`.

Gateway log: `[BATTLE] <- BattleGroundSpace(20001).openElement args=4003000001`.

Close uses the same entity: **`closeElement(INT32)`** = msgid **`0x89`**, sample `890800214e000040030000`.

Related (not OPEN): `uploadBlastState(INT32, BLOB)` = exposed index 11, msgid **`0x8B`** — **unverified** (no packet in the extract).

---

## 3. Pickup → which entity and method

Tapping an item in the Nearby list calls:

**`DtsProp.tryPickUp(INT32, BOOL)`** on that prop entity (ids ≥ 30000).

| Item | Value |
|------|--------|
| Exposed index | **1** (of 4 on DtsProp) |
| Message id | **`0x81`** |
| Sub byte | none |
| Length width | var16 |
| Arg types | `INT32`, `BOOL` |

### Captured hex (prop 30023)

Source: `logs/server.prev5.log`. File: `client/frida/payloads/requests/try_pickup_30023.hex.txt`.

```text
810900477500000100000001
```

Breakdown: `81` | len `0900` | eid `47750000` (30023) | `01000000` | `01`.

Gateway log: `[BATTLE] <- DtsProp(30023).tryPickUp args=0100000001`.

Teammate variant **`tryPickUpForTeammate(INT32, INT32)`** = msgid **`0x82`** — **unverified** (no packet this extract).

---

## 4. BattleGroundAvatar jump / parachute methods

Exposed cell methods (`.def` order via `bwdefs`; full table in `battle_cell_exposed.json`):

| Method | .def exposed index | Wire msgid (raw index) | Sub (raw) | Args | Packet status |
|--------|--------------------|-------------------------|-----------|------|----------------|
| `requestGetOffPlane` | 77 | `0xBC` | `0x13` on wire (client idx 79; −2 → 77) | `[]` (.def); wire had `ffffffff` | **verified** — `request_get_off_plane.hex.txt` |
| `chooseParachute` | 188 | `0xBC` | 128 (raw) / ~130 client-est. | `[]` | **unverified** |
| `chooseGlider` | 189 | `0xBC` | 129 (raw) / ~131 client-est. | `[]` | **unverified** |
| `fall` | 305 | `0xBC` | `0xF5` in capture | `[]` (.def); wire had `01` | **verified** — `fall.hex.txt` |

Avatar note: live decode uses `EXPOSED_SHIFT=2` for client indices ≥ 60 (`LOBBY_FINDINGS` update 13). Space/DtsProp need no shift. A live Frida dump (`dump_cell_methods.js`) was **not** re-run this session (`adb` unavailable); Avatar rows are `.def`-ordered and marked verified only when a log packet matched.

---

## 5. Messages `0xBC` and `0xBD` (position?)

**Verdict: not a dedicated position packet.** Field layout as “position update”: **unknown / not applicable**.

| Msg | Role on this client | Evidence |
|-----|---------------------|----------|
| `0xBC` (`188`) | First **extended** BattleGroundAvatar cell-method msgid (`eff=60`) | Thousands of samples in `server.prev5.log`; e.g. `onRecvClientFPS(30)` payload `00000000e71e000000` |
| `0xBD` (`189`) | Next extended msgid (`eff+1`) for indices `60+256+sub` | 92 samples in the same log; e.g. payload `000000000b00000000` |
| ClientInterface **3** | Later identified as the position path (header + xyz float32) | `LOBBY_FINDINGS` update 16 — layout details outside this task’s verified set |
| ClientInterface **2** | Often bundled with 0xBC; float-looking payload | Present in captures; **layout unknown** |

Early lobby notes that labelled 0xBC/0xBD as position updates predated the Avatar extended-method decode. Samples: `client/frida/payloads/requests/msg_0xbc_0xbd_samples.hex.txt`.

---

## 6. Extract JSON and verification rule

`server/extract/battle_cell_exposed.json` lists every exposed cell method for `BattleGroundAvatar`, `BattleGroundSpace`, and `DtsProp` with:

- `index`, `name`, `args`
- `msg_id` / `msg_id_hex`, `sub_byte`, `length_width` (`var16`)
- `verified` + `evidence` (packet path or `unverified`)

**Checked against a captured packet:** `openElement`, `closeElement`, `tryPickUp`, `requestGetOffPlane`, `fall`, plus several Avatar methods named in live logs (`jumpStart`, `changePose`, `fire`, …). **All other ids: `verified=false` / evidence `unverified`.**

---

## 7. How to refresh from the client

1. Enter a match on LDPlayer.
2. `python scripts/run_frida.py frida/dump_cell_methods.js --attach --realm emulated`
3. If cell offsets fail, set `SCAN = true` in the script once and re-attach.
4. Merge `[map]` blocks into `battle_cell_exposed.json` (prefer live names over `.def` if they differ).
5. Press OPEN and pick up one item; confirm hex against section 2–3.

# Bot (Robot) entities — original client evidence (RO-068)

**Status:** research only. `compatibility_status` stays **researching / unknown**.  
This is not an original-server compatibility claim and does not invent opcodes.  
Fair combat AI is later (RO-111). First spawn work is RO-069.

Sources used in this pass:

- `server/extract/client_entity_types.json`, `server/extract/entities_out/130_3298c23a.bin` (`defs/robot.def`)
- `bwdefs.Defs()` property / ClientMethods / CellMethods tables
- Prior framing evidence: `docs/CREATE_ENTITY_FRAMING.md`, `docs/CREATE_ENTITY_FORMAT.md`, `docs/ENTITY_PROPERTY_UPDATE_FORMAT.md`, `docs/BATTLE_CLIENT_REQUESTS.md`, `docs/LOBBY_FINDINGS.md`
- Offline sample builder: `client/frida/payloads/bots/_ro068_probe_indices.py`

No live Robot spawn was sent to a device in this task. Live checks that exist are for Space / Plane / Avatar framing and for Avatar method ids (RO-056 / RO-057).

---

## 1. Entity type decision

| Client type id | Name | Role |
|---|---|---|
| **58** | **Robot** | Dedicated BR bot entity. Use this for RO-069. |
| 59 | RobotImba | Variant; same create shape (~124 ALL/OTHER props). Skip for first bots. |
| 64 | RobotRos2 | Variant; create list 123. Skip for first bots. |
| 43 | Avatar | Hall / tutorial style entity. Has `nickname` / `robotVisible` too, but is not the BR bot type. |
| 120 | BattleGroundAvatar | **Player** in a match. Do not spawn bots as this type. |

**Verdict:** bots use **`Robot` (type 58)**, not an Avatar-like player entity.  
`MatchSession.alloc_bot_id()` already reserves ids from **40000+** for Robot / bots (`server/battle/session.py`).

`robot.def` implements combat/move interfaces (`iCell`, `iMove`, `iRotate`, `iNormalCombatUnit`, `iCombatBehavior`, `iDtsEquip`, …) and sets `<ClientName>Robot</ClientName>`. It is a separate client entity class from `BattleGroundAvatar`.

---

## 2. Property lists (measured)

| List | Count | Rule |
|---|---|---|
| createEntity (ALL_CLIENTS / OTHER_CLIENTS) | **124** | `desc+0x88` / `battle_flow.other_client_props` |
| property-update (`flags & 6`) | **161** | `desc+0x70` / same rule as `ENTITY_PROPERTY_UPDATE_FORMAT.md` |
| All properties (every flag) | 301 | includes CELL_PRIVATE etc. |

Task text that said “125 client-visible” is close to the create list; the measured create list is **124**. Do not treat create indices as update indices (e.g. `nickname` create **122** vs update **159**).

`updateEntity` (ClientInterface id **10**) is **not** the live property path on this client (RO-056 static + notes). Use `0xC0|idx` / `0xFD` path updates (`ENTITY_PROPERTY_UPDATE_FORMAT.md`). Non-player property updates are **statically** supported; **live Robot updates are unverified**.

### 2.1 Minimum set to render a named humanoid

Send `enterAoI` + `createEntity` with mask mode (RO-056). Put the body at the createEntity **header** position / packed yaw. Override only:

| Property | Type | Why |
|---|---|---|
| `mapID` | INT32 | Match map (700 in current gateway tests). |
| `characterType` | UINT32 | Humanoid model. Use normal heroes **20001** (male) / **20002** (female) per `hero_rules` / LOBBY_FINDINGS. Do not use hall placeholder **30001** as a bot body. |
| `nickname` | STRING | Nameplate text (`bwdefs.blob` / packed length + UTF-8). |
| `robotVisible` | BOOL | Default in `.def` is **1**; send `1` explicitly. |
| `hp`, `maxHp` | INT32 | Non-zero so the unit is not born “empty”. Exact original values **unknown** — use a local placeholder (e.g. 100) and keep compatibility unknown. |
| `gender` | INT32 | Appearance; `.def` default elsewhere is often 2 — send 1/2 to match `characterType`. |
| `level` | INT32 | Nameplate level; default 0. |
| `battleState` | INT8 | Keep 0 (alive / normal) until death research. |
| `pose` | INT8 | Stand (0) unless a later capture says otherwise. |

**Mask to defaults (do not invent wire values):**

- `campType` (`CAMP_TYPE`, `<implementedBy>` converter) — same caveat as DtsProp / CREATE_ENTITY_FORMAT.
- All weapon FIXED_DICTs, PYTHON fields, dress lists, jet/paraglider fields.

`planeID` exists on Robot (create idx 24). First-playable bots that only need ground visibility can leave it default **0**. Plane boarding for bots is out of scope for RO-068/069 minimum bar unless a later capture requires it.

### 2.2 Offline sample (encoder evidence, not a live capture)

Built with `battle_flow.create_entity` + `bwdefs.blob` (script above):

```text
enterAoI + createEntity Robot eid=40000 type=58
pos=(845, 50, -2467) yaw≈0.5
overrides: mapID=700, characterType=20001, hp=maxHp=100, gender=1, level=1,
           battleState=0, pose=0, nickname="Bot01", robotVisible=1

hex (82 bytes):
0b409c0000ff094900409c00003a00004053440000484200301ac5140000000001
6efbfffbf7fffffffffffff7ffffff01bc020000214e00006400000064000000
0000010000000100000005426f74303101
```

Parse check: `0b` enterAoI eid `0x00009c40` (40000); `09` createEntity; type `0x003a` (58); then RO-056 property stream (`flag=0`, `compression=0`, `mask_flag=1`, 16-byte mask for 124 bits, then selected values).  
**Live Robot accept/reject on LDPlayer is still open** (see remaining_issues).

---

## 3. Movement synchronisation

### 3.1 What is **not** bot position

RO-057: ClientInterface / entity messages **`0xBC` / `0xBD` are BattleGroundAvatar extended cell-method ids**, not a dedicated position packet. Do not reuse them as “bot move” messages.

Client→server **own player** position is ClientInterface message **3** (header + xyz float32 used by `Match.on_position`). That path is for the local avatar, not for pushing Robot transforms to other clients.

ClientInterface message **10** `updateEntity`: **unknown / unused** for property or movement on this build (RO-056).

### 3.2 Declared volatile fields (`robot.def`)

```xml
<Volatile>
  <position/>
  <yaw/>
</Volatile>
```

Avatar’s own `.def` also declares volatile position/yaw (plus pitch/timestamp). `BattleGroundAvatar.def` has no local `<Volatile>` block (inherits via parent chain).  
So the client expects **server-driven position + yaw** for Robot after create.

### 3.3 Candidate S2C position messages (named; layouts unevenly evidenced)

| Message | Id | Size note | Evidence | Bot use |
|---|---|---|---|---|
| createEntity header | 9 | `3×f32` pos + `3×int8` packed yaw/pitch/roll | **Verified** framing (RO-056); offline Robot sample above | Initial spawn pose |
| forcedPosition | **0x59** | fixed **36** | Live **own avatar** teleport accepted: `eid u32, spaceID u32, vehicleID u32, pos 3×f32, dir 3×f32` (`LOBBY_FINDINGS` plane/jump; `battle_flow` `tp`; `jump.forced_position`) | **Candidate** sparse relocate for a Robot eid; **not live-tested on Robot** |
| detailedPosition | **0x58** | fixed **30** | Named in message map / `battle_flow` header comment only | **Layout unknown** — do not invent bytes for RO-069 |
| leaveAoI + createEntity | 15 + 9 | full recreate | Live Space recreate needs leave first (RO-056 RESEND) | Teleport-by-recreate; not continuous move |

**Documented movement layout with captured evidence (this task):**

1. **Initial:** createEntity position + packed direction (RO-056 layout; sample hex above).  
2. **Ongoing:** intended channel is volatile **position/yaw**, almost certainly via ClientInterface **detailedPosition (0x58)** and/or **forcedPosition (0x59)**. Only **0x59** has a partially captured layout, and only for the **player** avatar. Robot continuous walk sync remains **unknown**.

RO-069 should not invent a 0x58 payload. Prefer: spawn with createEntity pose; optional rare `forcedPosition` experiments logged as unverified; no fake “walk packet” opcodes.

---

## 4. Kill feed and `aliveNum`

### 4.1 `aliveNum`

- Property of **`BattleGroundSpace`**, create index **72** (INT32).  
- Live HUD “N LEFT” updates when the space entity is created/updated with `aliveNum` (`LOBBY_FINDINGS` countdown).  
- Creating Robot entities does **not** by itself change `aliveNum`. The gateway must set `aliveNum` to **1 human + N bots** (or whatever the match rule is) via create mask or a later property update.  
- First bot task: set space `aliveNum` explicitly; do not assume auto-count.

### 4.2 Kill feed

Client methods present on **both** `Robot` and `BattleGroundAvatar` (indices differ):

| Method | Robot client idx | BattleGroundAvatar client idx | Args |
|---|---|---|---|
| `dtsKillTip` | 95 | 262 | `STRING` |
| `onBattleGroundDie` | 96 | 263 | `PYTHON` |
| `showKillerOverview` | 109 | 276 | FIXED_DICT + ARRAY |
| `die` | 25 | 192 | combat die args |
| `damage` | 23 | 190 | combat damage args |

**Inference (not live-proven):** kill-feed UI is driven by server→client methods such as **`dtsKillTip(STRING)`** on **observing** entities (typically the local `BattleGroundAvatar`), not by Robot create alone. Exact string format and whether Space also participates are **unknown**.

Cell-side (server script) names on Robot include `fakeDie`, `onShootKillOther`, `updateBattleKillNum` (on battle interfaces). Those are not ClientInterface opcodes by themselves.

---

## 5. Hitting a bot without a server reply

**C2S (client can send without waiting):** Robot exposes cell methods including:

- `shootHit(SHOOT_WEAPON_INFO, VECTOR3, ENTITY_ID, HIT_PART, VECTOR3, INT32)` — owner `Robot`, exposed  
- `checkShootHit(...)` — `iCombatBehavior`, exposed  
- `broadcastShootHitEntity(...)` — `iNormalCombatUnit`, exposed  

So the shooter can report a hit toward a Robot entity id. Wire msg ids for those Robot exposed indices were **not** captured in this pass (Avatar shift rules from RO-057 do not automatically apply to Robot).

**S2C needed for visible damage / death:**

- Property updates: `hp` / `tmpHP` / `actualHP`, `deadInGame`, `dieReason`, maybe `woundCount`  
- and/or client methods: `damage(...)`, `die(...)`, optionally `onBroadcastShootHitEntity` on witnesses  

**Verdict:** a bot is **unlikely** to show authoritative HP loss, death pose, or kill feed from local prediction alone. Local muzzle / hit FX for the shooter’s own weapon may still play; that is separate from Robot state. **First bot task (RO-069) should skip combat replies** (no `damage`/`die`, no hp combat loop, no `dtsKillTip`).

---

## 6. What the client does when a bot dies (evidence vs gap)

From `.def` / method tables only:

1. Server may call client `die(...)` on the Robot and/or set `deadInGame=True`, `dieReason=…`.  
2. Server may call `fakeDie` on the cell (not exposed) — script-side; client effect unknown.  
3. Observers may get `dtsKillTip` / related battle methods.  
4. Space `aliveNum` should decrease via property update.  
5. Entity may later `leaveAoI` / destroy.

**Live ragdoll, corpse lifetime, loot crate, and whether the model stays** are **not observed**. List under remaining_issues. Do not implement death for RO-069.

---

## 7. Damage / death: needed vs first-bot skip

| Concern | Needs from server (research) | RO-069 first bots |
|---|---|---|
| Visible named humanoid | createEntity Robot + min props + pose | **Do** |
| Count in “N LEFT” | Space `aliveNum` include bots | **Do** |
| Walk/run sync | volatile pos/yaw via 0x58/0x59 (layout TBD) | **Skip continuous sync** until 0x58 captured; static or rare unverified 0x59 only if needed |
| Take damage from player | hp updates and/or `damage` | **Skip** |
| Die / kill feed | `die`, `deadInGame`, `dtsKillTip`, `aliveNum--` | **Skip** |
| Fair AI / shooting back | RO-111 | **Skip** |
| Variants RobotImba / RobotRos2 | separate types | **Skip** (use 58) |

---

## 8. Frida payloads

Under `client/frida/payloads/bots/`:

| File | Purpose |
|---|---|
| `_ro068_probe_indices.py` | Offline indices + sample createEntity hex |
| `robot_entities_check.py` | Live NeoX probe: list `Robot*` in `BigWorld.entities`, read nickname / characterType / position |

---

## 9. remaining_issues

1. Live LDPlayer accept of masked Robot createEntity (stream errors / model / nameplate).  
2. Exact **detailedPosition (0x58)** 30-byte layout for Robot volatile position/yaw — **do not invent**.  
3. Whether **forcedPosition (0x59)** with a Robot eid moves the bot the same way as the player teleport.  
4. How often original servers emit volatile updates (rate / filter / AoI).  
5. `dtsKillTip` STRING format and which entity receives it for a bot kill.  
6. Client death visuals for Robot (`die` vs `deadInGame` vs `fakeDie` vs leaveAoI).  
7. Whether player weapons register hits on Robot without any S2C (local-only FX).  
8. Safe non-default `campType` bytes (converter).  
9. Robot exposed cell-method wire ids / any index shift (RO-057 Avatar shift is not evidence for Robot).  
10. Whether bots must set `planeID` / join the plane for first-playable “drop with bots” UX, or ground spawn is enough for the RO-069 visibility bar.

---

## 10. Compatibility note

| Field | Value |
|---|---|
| implementation_status | not_implemented (no gateway Robot spawn yet) |
| test_status | none in this task (registry validators only) |
| compatibility_status | **unknown** / researching |
| original_reference | client `.def` + prior gateway captures; no authorized original-server oracle |

Recommend **protocol-test-engineer** review of message id / property-index claims before RO-069 sends traffic.

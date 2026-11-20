# ClientInterface createEntity: property-data layout (original client)

Static analysis of `libclient.so` (arm64, the sibling copy in `RosGG/extract`), cross-checked with the
`.def` files in `server/extract/entities_out`. Nothing here was tried on a live client in this pass.
Addresses are file virtual addresses of that `libclient.so`.

## 1. Result in one paragraph

`createEntity` (client message id 9, var16) is `id u32, type u16, position 3 x float32, direction
3 x int8, flag u8, <compression-wrapped property stream>`. The "2 header bytes" you saw are the **flag
byte** (`00`, a bool that is stored on the entity) and the **compression type byte** (`00` = none).
The property stream that follows is read by `EntityType::newDictionary(stream, mode 3)`, which starts
with **one more byte (the "mask flag")** that your current data does not have. With mask flag `00` all
properties follow in order; with a non-zero mask flag a bitmask of `ceil(N/8)` bytes follows and every
property whose bit is set is NOT on the stream (the client fills in its `.def` default).
`battle_flow.prop_data` leaves that byte out, so the client takes the low byte of the first value
(`0xBC` of `mapID` 700) as a non-zero mask flag and eats the next 12 bytes as a bitmask. That alone
reproduces your logs exactly (see 3). Second bug: duplicated property names are listed twice
(BattleGroundSpace: `gameStatus`), and a property that is redefined with a different flag
(`gameUUID`: CELL_PUBLIC in `DynamicSpace`, ALL_CLIENTS in `BattleGroundSpace`) must sit at its FIRST position.

## 2. Wire layout

```
createEntity payload (message id 9, var16 length)
  u32  entity id
  u16  client entity type index (client_entity_types.json)
  3 x float32  position
  3 x int8     yaw, pitch, roll   (value * pi/128 radians; constant 0x2a24e4c)
  u8   flag    "onGround"-like bool, stored at entity+0x5c. Use 0.
  --- CompressionIStream starts here ---
  u8   compression type: 0 = none, 1..9 and 10 select a decompressor, anything else logs
       "CompressionIStream::CompressionIStream: Invalid compression type: N". Use 0.
  --- newDictionary(stream, 3) ---
  (if no bytes remain here at all: the client builds the default dictionary, see 5)
  u8   mask flag: 0 = every property is on the stream
                  !=0 = a bitmask follows
  [ceil(N/8) bytes bitmask]   N = number of ALL_CLIENTS/OTHER_CLIENTS properties of the entity.
                  bit i = byte[i >> 3] >> (i & 7) & 1 ; bit set = property i is NOT on the stream (default)
  property values in list order (only those whose bit is clear)
```

Evidence (all in `libclient.so`):

- Handler `0x94d6b0`: reads `u32` (4 bytes), `u16`, 12 bytes (position), 4 single bytes. Bytes 1-3 are
  multiplied by `pi/128` (`sxtb`, `scvtf`, `fmul` with the constant at `0x2a24e4c` = 0.0245437) and
  become yaw/pitch/roll; byte 4 is the flag (`cmp w27,#0; cset`). It then constructs the
  `CompressionIStream` (`0x98c3c8`, call at `0x94d80c`) over the rest of the message and calls the
  virtual `ClientApp::createEntity` (`0x91ded4`) with the wrapped stream as the last argument.
- `CompressionIStream::CompressionIStream` (`0x98c3c8`): reads 1 byte; 0 -> pass through; 1..9 -> object
  `0x99c108(level)`; 10 -> object `0x99b9c0`; otherwise the "Invalid compression type" message
  (xrefs at `0x98c464` and `0x98c690`; the string starts at `0x2a464b0`, three bytes after where a
  naive scan finds it). Your note was right: byte 0 is the flag, byte 1 the compression type.
- `ClientApp::createEntity` (`0x91ded4`, error string xref `0x91e1dc`) calls `0x92efbc` (`0x91e280`),
  which first calls `EntityType::newDictionary` (`0x92e944`) with **mode 3**, then
  `0x92f01c` (create the Python entity from the dictionary).
- `EntityType::newDictionary` (`0x92e944`, "Failed to set %s" xrefs `0x92ea2c`, `0x92ec28`):

  | mode | property list used | caller |
  |---|---|---|
  | 0 / 1 | `0x9d3bf4` with domain mask 0xb / 0xe | `0x926274` (update properties of an existing entity) |
  | 2 | list at `desc+0x70`: every client-visible property (flag bits 1 or 2) | player entity creation |
  | **3** | **list at `desc+0x88`: flag bit 1 = OTHER_CLIENTS or ALL_CLIENTS** | **createEntity of a non-player** |

  Mode 3 flow: if `stream.remaining() == 0` -> default dictionary (`0x92e6fc`). Else
  `N = count(desc+0x88 list)`, read 1 byte (`0x92eb64`, the mask flag); if non-zero read
  `(N+7)>>3` raw bytes (`0x9d4914`) into a bit vector; then for i in 0..N-1: bit set -> default value
  (`0x9a3c2c`), else `DataDescription::createFromStream` (`0x9a4cdc` -> datatype vtable slot 0x58)
  and store it under the property name.
- The `desc+0x88` list is filled at `0x9d0b54..0x9d0b94`: every master property whose flag bit 1 is
  set (`0x9a361c`), in **master (parse) order**. The master vector (68-byte DataDescription entries)
  is built by `EntityDescription::parseProperties` (`0x9d22d4`): properties are appended in `.def`
  order; a name that already exists is replaced IN PLACE (log string "property %s.%s is being
  overridden", xref `0x9d2438`; the whole description is replaced, including type and flags).
  Nothing is sorted: no DetailLevel, no fixed-length-first, no alphabetical order.
- Flag values (table at `0x38c68c8`): CELL_PRIVATE 0, CELL_PUBLIC 1, OTHER_CLIENTS 3, OWN_CLIENT 4,
  BASE 8, BASE_AND_CLIENT 0xC, CELL_PUBLIC_AND_OWN 5, ALL_CLIENTS 7, EDITOR_ONLY 0x40. Bit 1 (value 2)
  is set only for OTHER_CLIENTS and ALL_CLIENTS. So the createEntity list does NOT contain OWN_CLIENT,
  CELL_PUBLIC_AND_OWN, BASE_AND_CLIENT or CELL_PUBLIC properties.
- Value framing (the datatypes, vtable slot 0x58 = createFromStream):
  - integers/floats: little endian, BOOL = INT8, VECTOR2/3 = 2/3 x float32.
  - STRING/BLOB/UUID: packed length (1 byte, or `FF` + 3 byte LE when >= 255) + bytes.
  - PYTHON (`PythonDataType::createFromStream`, `0x9c7c10`): packed length + pickle bytes. **No compression
    byte of its own.** Length 0 is an error ("Not enough data on stream to read value", the check is
    at `0x9c7cb4`: stream error flag or empty string). So a PYTHON value must be a non-empty pickle.
  - ARRAY/TUPLE (`SequenceDataType::createFromStream`, `0x9a8e5c`): if the type has `<size> N` there is no
    count, N elements follow; otherwise an int32 count. The count is rejected ("Invalid size on stream: %d (%d bytes
    remaining)") when negative or **larger than the bytes remaining**.
  - FIXED_DICT: fields in `.def` order (as bwdefs does; unchanged by this analysis). See 4 for the
    `<implementedBy>` caveat.

## 3. Why the current stream fails (reproduced offline)

I wrote a small parser that follows the client logic above (mask flag, bitmask, list of
92 properties for BattleGroundSpace) and fed it the exact bytes `battle_flow.debug_command("space")`
produces (390 bytes after the direction). Result:

```
flag byte 00, compression 00, mask flag = 0xBC (low byte of mapID 700) -> 12 mask bytes eaten
... python empty at stream offset 28 (clientStatus)     -> "PythonDataType: Not enough data"
... redPacketCnt ends at 45, next read is an int32 count = 00 00 06 80 = -2147090432, 341 bytes remaining
                                                        -> "SequenceDataType: Invalid size -2147090432 (341 bytes remaining)"
```

That is the same pair of messages, the same number and the same "341 bytes remaining" as in your log, so
the model (mask flag byte, 92 entries, order) is confirmed by an exact numeric match, not only by reading code.
`00 00` then pickle `06 80 02 7d 71 00 2e` is just the next bytes of your stream at that point.

The `childBaseClientPropertyList` "+2" login bug is a **different** problem: there is no mask byte in
createBasePlayer, and there the client is 2 bytes AHEAD of the stream (it reads the `huiliuProgressAwardInfo`
count at element offset 72, we put it at 70). Lead, not verified: `FixedDictDataType` can have a Python-side
custom `createFromStream` (strings "createFromStreamCustom", "must implement both addToStream and
createFromStream, or implement neither"). `package2` is `DTS_APPEARANCE_REPERTORY_PACKAGE3`, implemented by
`package_common.PackageConvert3.dtsAppearanceRepertoryPackageConvert3`; if that class has custom stream methods,
its wire format is not the plain field list. The script source is not in this checkout, so this stays open.

## 4. Property lists and encoder check (task 2)

Corrected lists (dedupe rule: first position, last definition, then keep ALL_CLIENTS/OTHER_CLIENTS):

| entity (type) | N | notes |
|---|---|---|
| BattleGroundSpace (14) | 92 | old list had 93 (duplicate `gameStatus`: INT8 from DynamicSpace + INT32) and `gameUUID` at the end instead of index 2 |
| Plane (147) | 8 | unchanged: mapID, socketHint, moveSpeed, usedHangSockets, inJumpArea, movePath, mode, customPlan |
| DtsProp (140) | 10 | mapID, socketHint, groupID, propID, campType, amount, info, randomRotate, trainID, trainPosition |
| Robot (58) | 124 | |

BattleGroundSpace first entries: 0 mapID, 1 socketHint, 2 gameUUID, 3 gameStartTime, 4 gameStatus (INT32),
5 clientStatus (PYTHON), 6 gameEnterType, 7 weatherID, 8 redPackets, 9 redPacketCnt, ... 57 circleStage,
58 blueCircleCenter, 59 blueCircleRadius, 60 blueCircleStartRadius, 61 blueCircleStartCenter,
62 whiteCircleCenter, 63 preCalcCircleCenter, 64 preCalCircleHeight (PYTHON), 65 whiteCircleRadius,
66 planeEntityIDs, 67 openedElements, 68 blastObjectStates, ... 72 aliveNum, ... 74 getOnPlaneTime, ... 91 waitBornLeftTime.

Encoders in `bwdefs.encode_default` vs the client datatypes, for these four entities: all value types
(INT8/16/32, UINT8/32/64, FLOAT, BOOL, VECTOR2/3, STRING, BLOB, UUID(=BLOB), ENTITY_ID(=UINT32), PYTHON/PY_DICT,
ARRAY of scalar/VECTOR3/PYTHON/FIXED_DICT, FIXED_DICT) match the framing in section 2. No `<size>` array, no
`AllowNone` FIXED_DICT, no TUPLE and no USER_TYPE occurs in these four lists (`movePath` of
BattleGroundSpace is `<size>3`, but it is CELL_PUBLIC, so it is not sent). My parser accepts the full
default stream of all four entities with zero bytes left over (BattleGroundSpace 390, Plane 35, DtsProp 65,
Robot 1265 bytes incl. the 3 header bytes). Caveats that the offline parser cannot see:

- `buildUnitsMgr` (BattleGroundSpace, VOXEL_BUILDUNITS_MGR) and `campType` (DtsProp, Robot, CAMP_TYPE) are
  FIXED_DICTs with `<implementedBy>` Python converters (`sandbox.VoxelBuildTypes...`, `camp_utils.campInfoConverter`).
  If those classes define their own `addToStream`/`createFromStream` the wire format is custom. Unknown.
  Safest: leave them to the mask (default value).
- A PYTHON value with a `None` default is encoded by bwdefs as pickled `{}`; the real server sends `None`
  (`80 02 4e 2e`). For the space entity use None unless a script needs a dict.
- `gameStatus`, `socketHint`, `mapID` etc. exist in the client under their last definition; only the INT32
  `gameStatus` is on the wire.

## 5. Corrected builder

Drop-in for `battle_flow.prop_data` / `create_entity`. Mask mode sends only the values you name (best first
experiment: tiny, and it skips converters and PYTHON values). Full mode sends everything.

```python
import struct, bwdefs

OTHER_CLIENT_FLAGS = ("ALL_CLIENTS", "OTHER_CLIENTS")


def other_client_props(defs, entity):
    """The client's createEntity property list (desc+0x88): .def parse order (Parent, <Implements> in
    order, own); a re-defined name keeps its FIRST position and takes the LAST definition (type and
    flags); then keep ALL_CLIENTS / OTHER_CLIENTS only."""
    order, last = [], {}
    for p in defs.properties(entity):            # (name, typeText, flags, owner)
        if p[0] not in last:
            order.append(p[0])
        last[p[0]] = p
    return [last[n] for n in order if last[n][2] in OTHER_CLIENT_FLAGS]


def create_entity_data(defs, entity, values, on_ground=0, use_mask=True):
    """Bytes after the 3 direction bytes of createEntity:
       [flag u8][compression u8 = 0][mask flag u8][bitmask][values...]
    values: {propName: encoded bytes}. use_mask: send only `values`, everything else = client default."""
    props = other_client_props(defs, entity)
    names = [p[0] for p in props]
    for n in values:
        assert n in names, f"{entity}.{n} is not an ALL/OTHER_CLIENTS property"
    head = bytes([on_ground & 1, 0])
    if use_mask:
        mask, body = bytearray((len(props) + 7) // 8), b""
        for i, (name, typ, flags, owner) in enumerate(props):
            if name in values:
                body += values[name]
            else:
                mask[i >> 3] |= 1 << (i & 7)     # bit set = use default, nothing on the stream
        return head + b"\x01" + bytes(mask) + body
    body = b"".join(values[n] if n in values else
                    bwdefs.encode_default(defs.resolve(t), defs.defaults.get(n))
                    for n, t, _, _ in props)
    return head + b"\x00" + body


def create_entity_msg(defs, client_types, eid, entity, pos, ypr_i8, values, **kw):
    payload = (struct.pack("<IH", eid, client_types.index(entity)) + struct.pack("<3f", *pos)
               + struct.pack("<3b", *ypr_i8) + create_entity_data(defs, entity, values, **kw))
    return (bytes([11]) + struct.pack("<IB", eid, 0xFF)                    # enterAoI
            + bytes([9]) + struct.pack("<H", len(payload)) + payload)      # createEntity


i32 = lambda v: struct.pack("<i", v)
f32 = lambda v: struct.pack("<f", v)
i8 = lambda v: struct.pack("<b", v)
vec2 = lambda x, y: struct.pack("<2f", x, y)
vec3 = lambda x, y, z: struct.pack("<3f", x, y, z)
arr_i32 = lambda a: struct.pack("<I", len(a)) + b"".join(i32(v) for v in a)
arr_vec3 = lambda a: struct.pack("<I", len(a)) + b"".join(vec3(*v) for v in a)

# BattleGroundSpace: map 700, safe zone circle, one plane
space_values = dict(
    mapID=i32(700), gameStatus=i32(1), gameStartTime=i32(0), aliveNum=i32(100), getOnPlaneTime=i32(0),
    circleStage=i32(1),
    whiteCircleCenter=vec2(845.0, -2467.0), whiteCircleRadius=i32(300),
    blueCircleCenter=vec2(845.0, -2467.0), blueCircleRadius=i32(1200),
    blueCircleStartCenter=vec2(845.0, -2467.0), blueCircleStartRadius=i32(1200),
    planeEntityIDs=arr_i32([20002]),
)
# Plane: map 700, two way points, speed 60, not in jump area
plane_values = dict(
    mapID=i32(700), moveSpeed=f32(60.0), inJumpArea=i8(0), mode=i32(0),
    movePath=arr_vec3([(0.0, 300.0, 0.0), (2000.0, 300.0, 2000.0)]),
)
```

The BattleGroundSpace data is 83 bytes in mask mode (390 in full mode) and the Plane data is 45 bytes (59 in full mode); both
parse to the end with no bytes left in my offline model of the client. The values (zone numbers, plane path) are
test numbers; `movePath` is a list of VECTOR3 as the plane script expects, the real flight path is unknown.
Replace `bwdefs.encode_default(...)` for PYTHON-with-None-default if a script needs `None`.

## 6. Experiments for the emulator (one message each)

Confidence: the framing (flag, compression, mask flag, bitmask, list order, value framing) is high, about 90 percent,
because the offline model reproduces the logged error text and the numbers exactly. That the entity then works in
game (scripts accept the values) is unproven. Run in this order with fresh matches (a bad message stalls the channel).
`trigger_battle.txt` `ce` takes `ce <eid> <Entity> <hex of everything after the 3 direction bytes>`:

1. Framing only, default dictionary (client must log nothing, entity exists):
   `ce 20002 Plane 0000`
   Expected: no "Not enough data", no "Invalid size", no "Invalid compression type"; `BigWorld.entities[20002]`
   is a Plane. If this fails the problem is in the header, not in the property data.
2. Plane via mask (8 properties, mask byte `8a` = socketHint, usedHangSockets, customPlan left to defaults):
   `ce 20002 Plane 0000018abc0200000000704200020000000000000000009643000000000000fa44000096430000fa4400000000`
   (that is `00 00 | 01 | 8a | mapID 700 | moveSpeed 60.0 | inJumpArea 0 | movePath: count 2, (0,300,0), (2000,300,2000) | mode 0`;
   my offline model parses it to the last byte). Expected: no stream errors; `BigWorld.entities[20002].mapID == 700`, `.moveSpeed == 60.0`, `len(.movePath) == 2`.
   (The hex above is the output of `create_entity_data(D, "Plane", plane_values)`; regenerate it with the code in section 5 to be safe.)
3. Space, mapID only: `ce 20001 BattleGroundSpace 000001feffffffffffffffffffff0fbc020000`
   Expected: no stream errors; `enterWorld` should now get past the `maps_utils` data None failure for map 700
   (that is the symptom in LOBBY_FINDINGS item 8). Then send `space_values` (83 bytes) for the zone.

If step 1 passes and step 2 or 3 logs a stream error, the log gives the position: the numbers in
"Invalid size" and "bytes remaining" tell where the client is. If a Python exception from a converter appears for
`buildUnitsMgr` or `campType`, keep those in the mask.

Fallback if everything about values fails: send step 1 (default dictionary) and set properties afterwards
with property-update messages (BigWorld style `0xC0|index`, index = position in this same 92/8 entry list for ALL_CLIENTS
properties; unverified on this client, see the note in `battle_flow.py`).

## 7. Door OPEN and prop pick-up: what the client calls (from the `.def` files)

There is no door entity in the battle. Doors and other level elements are state on the **space entity**.

Door / element (BattleGroundSpace, also BattleGroundTutorialSpace):

- Client -> server, exposed cell method on the space entity (`Globals.spaceEntity.cell...`):
  `openElement(INT32 elemID, INT8 state)` (exposed cell method 8 of 14) and `closeElement(INT32 elemID)` (9 of 14).
- Server -> client replies:
  - client method on the space entity `onElementOpen(INT32 elemID, INT8 state)` (client method 40 of 66) and
    `onElementClose(INT32 elemID)` (41 of 66);
  - property `openedElements` (ALL_CLIENTS, `ARRAY<DTS_ELEMENT>`, `DTS_ELEMENT = {elemID INT32, state INT8}`)
    updated to contain `{elemID, state}` (remove the entry on close). New clients get it with createEntity
    (index 67 in the BattleGroundSpace list).
  - The meaning of `state` is not in the defs (probably the open direction/side); mirror what the client sent.
- Vehicle doors are separate (`IVehicle.openDoor/closeDoor`, client `onOpenDoor/onCloseDoor`, property `doorOpened`);
  `ElevatorCage`/`DungeonSpace` also have `openDoor`. Not the battle door.

Pick up props:

- The pickable world item is a `DtsProp` entity (type 140; properties groupID, propID, campType, amount, info,
  randomRotate, trainID, trainPosition). Client -> server: exposed cell method on that entity
  `tryPickUp(INT32, BOOL)` (exposed 1 of 4) and, for a teammate, `tryPickUpForTeammate(INT32 , INT32)` (2 of 4).
  The first INT32 is probably the avatar entity id, the BOOL unknown; log the first call.
- Also exposed on the player (`Avatar`) cell: `onPickUpProp(BOOL)`; it is the client reporting the pick animation/ack
  (name suggests a callback, semantics unverified).
- Server -> client:
  - add the item to the avatar's `dtsItemPackage` (`DTS_PACKAGE3`, BASE_AND_CLIENT, interface `iDtsPackage`) via a property
    update, or for ammo/attachments the matching `dts*`/weapon properties;
  - `onUpdateShowPickNum(INT32)` on the avatar (iDtsProp, client method 749 of 763 in the deduped table; property
    `showPickNum` is BASE_AND_CLIENT) when the pick counter changes;
  - `onPickUpPropEntity()` on the avatar (no arguments, iDtsProp) and the avatar client method `onPickUpProp(BOOL)` look
    like the confirmation hooks; `DtsProp.syncAmount(INT32)` (client method 17 of 19) lowers the amount when only part
    of a stack was taken;
  - remove the world item with `leaveAoI(propEntityId)` (msg 15) when it is fully taken.
- Other pick-ups seen in the defs, not needed now: `AutoRoyaleProp/DtsRos2AirDrop/TrainCarriageSupply.tryPickUp`,
  `onPickUpCrazyCarnivalItem`, `onPickUpOutGameItem`.

Client scripts are not available here, so the argument meanings above come from the `.def` signatures only. To confirm
without guessing, log the first real `openElement` / `tryPickUp` the client sends (entity id, exposed index and bytes) and
answer with the shapes above.

Method indices quoted are indices in the raw `.def` order of this `bwdefs` version (the gateway's `client_method_ex`
uses the raw table); the deduplicated table differs for BattleGroundAvatar (`onPickUpProp` raw 627, dedup 625).
For BattleGroundSpace and DtsProp raw and dedup are equal.

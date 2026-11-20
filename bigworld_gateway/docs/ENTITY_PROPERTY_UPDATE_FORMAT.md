# ClientInterface entity property update (original client)

Static analysis of `libclient.so` (arm64, `RosGG/extract` copy). Nothing here was tried on a live client.
Addresses are file virtual addresses. Same method as `CREATE_ENTITY_FORMAT.md`.

## 1. Result

Property updates are NOT in the method id range and NOT `updateEntity` (id 10). They are entity messages
with the property id range `0xC0..0xFF`:

| wire id | length | meaning |
|---|---|---|
| `0x80..0xBF` | var16 | method call (as already used) |
| `0xC0 + p`, p = 0..60 (`0xC0..0xFC`) | var8 (1 byte) | property update, direct: p is the client property index, the value follows |
| `0xFD, 0xFE, 0xFF` (p = 61..63) | var16 | property update with a bit-packed path (needed for index >= 61) |

Payload (both forms): `entity id u32 LE`, then (only for 0xFD..0xFF) the bit path, then the value.
The value is the WHOLE new property value in the same framing as in createEntity (`DataDescription::createFromStream`,
see CREATE_ENTITY_FORMAT section 2). There is no mask flag, no compression byte, no count.
Own player and other entities use the same message and the same index space.

Evidence:
- `EntityMessageHandler::handleMessage` (`0x94bbf0`): `w20 = header.id & 0x7f`; reads the u32 entity id; `tbnz w20,#6`
  -> property handler (vtable +0x40) with `idx = w20 & 0x3f`, else method handler (+0x48) with `idx = w20`.
  So ids 0xC0+p and 0xFD..0xFF are properties, 0x80..0xBF methods. The "did not consume all data" text (`0x94bd50`) is this function.
  Buffered messages for entities not yet entered use the same rule (`0x91d690`: bit 6 -> `0x9260d0` -> propertyEvent).
- `propertyEvent` (`0x9644a4`; strings "SimpleClientEntity::propertyEvent: No property starting with message id %d",
  "propertyEvent: illegal value of property %s", xrefs `0x96479c`, `0x964640`). It calls the path decoder `0x9a4600`
  (its only caller; the method lookup is the different function `0x9d46f8`).
- Path decoder `0x9a4600(root, msgIdx, stream, outPath)`:
  - `msgIdx <= 60`: path = [msgIdx], no stream bits, container = root.
  - `msgIdx == -1` branch (reads a count byte + u32 list): not reachable from the dispatcher (idx is masked to 0..63).
  - `msgIdx > 60` (0xFD/0xFE/0xFF, all identical): MSB-first bit stream, bytes fetched lazily from the message. Per level: container
    child count `n` (vtable +0x18; root = `0x9d4634` = size of the property list at `desc+0x70`); index width = `bit_length(n-1)` bits
    (0 bits if n is 0 or 1); for a variable-size container (n < 0, arrays) a prefix selects the width: bit `0` -> 6 bits, `10` -> 13 bits,
    `11` -> 32 bits. Then the child is looked up (vtable +0x20) and a 1-bit "more" flag is read: 1 = descend into the child and read
    another level, 0 = last level. The global byte `0x44e06d8` ("enableFixPropertyPathSyncBug") only decides whether the more-bit is
    also consumed when the child is a leaf. For a whole-value top-level update the path is 9 + 1 = 10 bits either way (2 bytes), so the
    stream is identical with the flag on or off provided the more-bit is 0. The value starts at the next byte boundary.
  - The path is stored reversed (leaf index first); the returned container is the parent of the last index.
- Root `set` (vtable +0x28, `0x964ac4`): takes `path[0]`, looks up the DataDescription at that client index (`0x9d4644`, list `desc+0x70`),
  `createFromStream` (`0x9a4cdc`), reads the old value (getattr), sets the new one (setattr), so script `set_<name>` hooks run. At
  root level the whole property is replaced.

### Index space (the important detail)

The client index is the position in the list at `desc+0x70` (filled at `0x9d0b10`, test `0x9a3634` = `flags & 6 != 0`),
in `.def` parse order, a re-defined name keeping its FIRST position and its LAST definition (as for createEntity). Qualifying flags
(table `0x38c68c8`, aliases included): OTHER_CLIENTS/OTHER_CLIENT 3, OWN_CLIENT 4, CELL_PUBLIC_AND_OWN/GHOSTED_AND_OWN/CELL_AND_OWN 5,
ALL_CLIENTS/ALL_CLIENT 7, BASE_AND_CLIENT 0xC. Not included: CELL_PRIVATE/PRIVATE 0, CELL_PUBLIC/CELL/GHOSTED 1, BASE 8, EDITOR_ONLY 0x40.
The client startup log "client top-level property count = N. Efficient to 61" (`0x9d623c`, count function `0x9d4634`) prints exactly this
count; "Efficient to 61" is the direct range (index < 61, ids 0xC0..0xFC). Because BASE_AND_CLIENT is included the list is larger than
the 388 own-cell list:

- BattleGroundAvatar: N = 495 (9-bit index); dtsWeapon1 = 423, dtsWeapon3 = 425, dtsCurWeapon = 431. (327 is the position in the
  cell-own list of createCellPlayer, a different list.)
- Same rule: BattleGroundSpace 95, Plane 11, DtsProp 13, Robot 161, Athlete 720 (equals the known client log value).
- Non-player entities use the same list (propertyEvent does no OTHER_CLIENTS filtering), so the index is NOT the createEntity-list index
  for entities that also have OWN_CLIENT / CELL_PUBLIC_AND_OWN / BASE_AND_CLIENT properties (Space 92 vs 95, Plane 8 vs 11, DtsProp 10 vs 13).

### Nested / FIXED_DICT / ARRAY

The stream is a PATH, not only a value: more-bit 1 descends. A FIXED_DICT is a container whose children are its fields
(index width bit_length(nFields-1)); arrays are variable size (6/13/32-bit prefix scheme). The leaf value is the element/field value
(createFromStream of the sub-type). Array slice operations may use further handlers that were not decoded. A whole FIXED_DICT/ARRAY
replacement is the plain root form (more-bit 0 + complete value), used in section 3 and the safe choice. Partial paths are unverified.

## 2. The earlier live observations

- 0xBF: method id 63 -> method lookup fails ("No method starting with message id 63"). Expected.
- 0xBE + sub byte 71: a METHOD call (index eff + 3*256 + 71), not a property. Nothing should change. Expected.
- 0xBD: a method taking no argument, so the INT32 stayed unread ("remain 4 bytes"). Expected.

## 3. Builder and exact messages

```python
import struct, bwdefs
_FL = {'CELL_PRIVATE': 0, 'PRIVATE': 0, 'CELL_PUBLIC': 1, 'CELL': 1, 'GHOSTED': 1, 'OTHER_CLIENTS': 3, 'OTHER_CLIENT': 3,
       'OWN_CLIENT': 4, 'BASE': 8, 'BASE_AND_CLIENT': 0xC, 'CELL_PUBLIC_AND_OWN': 5, 'GHOSTED_AND_OWN': 5,
       'CELL_AND_OWN': 5, 'ALL_CLIENTS': 7, 'ALL_CLIENT': 7, 'EDITOR_ONLY': 0x40, '': 0}


def client_prop_list(defs, entity):
    """Client property index list (desc+0x70): parse order, first position / last definition, flags & 6."""
    order, last = [], {}
    for p in defs.properties(entity):
        if p[0] not in last:
            order.append(p[0])
        last[p[0]] = p
    return [last[n] for n in order if _FL[last[n][2]] & 6]


def build_property_update(entity_name, eid, prop_name, value_bytes, defs=None):
    defs = defs or bwdefs.Defs()
    L = client_prop_list(defs, entity_name)
    idx = [p[0] for p in L].index(prop_name)
    n = len(L)
    if idx <= 60:                                   # direct: id 0xC0|idx, var8
        payload = struct.pack("<I", eid) + value_bytes
        return bytes([0xC0 | idx, len(payload)]) + payload
    nbits = (n - 1).bit_length()                    # bit path: index, more-bit 0, zero padding
    assert nbits + 1 <= 16
    path = (((idx << 1) | 0) << (16 - nbits - 1)).to_bytes(2, "big")
    payload = struct.pack("<I", eid) + path + value_bytes
    return bytes([0xFD]) + struct.pack("<H", len(payload)) + payload   # var16
```

(For n > 32768 or paths deeper than one level the bit packing needs a general writer; not needed here.)

Messages for entity id 10003 (generated offline with the code above; not sent to a client):

```
dtsCurWeapon = 7 (INT32, index 431):
fd0a0013270000d78007000000

dtsWeapon3 = 1301 (INT32, index 425):
fd0a0013270000d48015050000

dtsWeapon1 = weaponID 1001, other fields bwdefs defaults (FIXED_DICT, index 423, 96 bytes):
fd5d0013270000d380e90300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000680027d71002e0680027d71002e
```

Layout of the first message: `fd` id, `0a00` length 10, `13270000` entity 10003, `d780` path (9-bit index 431 = `1 1010 1111`,
more-bit 0, 6 padding bits), `07000000` value. The dtsWeapon1 value is `value = pack("<I",1001) + encode_default(resolve("BATTLE_GROUND_WEAPON_ITEM"), None)[4:]`
(87 bytes: 19 fixed fields, an empty STRING, two PYTHON fields as pickled `{}`).

## 4. Confidence and expected client log

- Id range, var8/var16, entity id first, whole-value framing, bit path, list rule (`flags & 6`, list `desc+0x70`): high, about 85 percent;
  every step was read from the code, nothing ran live.
- The exact count 495 and indices 423/425/431 depend on bwdefs reproducing the client's property parse (it did for createEntity).
  An off-by-few index keeps the 9-bit width but hits another property: read the attribute afterwards.
- Unknown: custom stream format of the `implementedBy` converter of `BATTLE_GROUND_WEAPON_ITEM` (same caveat as createEntity); the
  `ros2WeaponInGame*Infos` PYTHON fields use bwdefs' pickled `{}`.
- Success: no "SimpleClientEntity::propertyEvent" and no "did not consume all data" in the log; `BigWorld.player().dtsCurWeapon == 7`
  (and `dtsWeapon3 == 1301`, `dtsWeapon1['weaponID'] == 1001`); `set_<prop>` script hooks run (dtsWeapon1 may touch model/UI).
- Failure signatures: "No property starting with message id 61" = path decode found no container (bad index/count);
  "propertyEvent: illegal value of property X" = index hit a property whose value could not be set; "Not enough data on stream" /
  "Invalid size" = wrong property (different type); "did not consume all data, remain N bytes" = value longer than the type reads;
  a different attribute changed = index list off by some entries. Send one message per fresh match; a bad message stalls the channel.

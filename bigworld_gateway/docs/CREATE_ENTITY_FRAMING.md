# Original client `createEntity` framing

**Status:** the entity creation header and the non-player property stream are supported by static
analysis and live emulator observations (RO-056, 2026-11-26 resume). Property-update framing and
server-to-client non-player method calls remain partially unverified. This is research evidence for
the gateway; it does not define this repository's versioned JSON API or establish compatibility with
an original Rules of Survival server.

## Wire layout

For ClientInterface message 9 (`createEntity`, var16), the payload is:

```text
u32 entity id
u16 client entity type
3 * float32 position
3 * int8 packed yaw/pitch/roll
u8 flag
u8 compression type
u8 property mask flag, when property bytes remain
[ceil(N / 8) mask bytes, when the mask flag is nonzero]
property values in the selected list order, omitting values whose mask bit is set
```

`enterAoI` is a separate fixed-size message sent before `createEntity` (message 11, entity id plus
alias). The direction bytes encode angle as signed byte times `pi / 128`. The flag is read as a
boolean; the gateway's test messages use `0`. Compression type `0` passes the following bytes
through unchanged. Values 1–10 select decompression paths; other values produce
`CompressionIStream::CompressionIStream: Invalid compression type: N`.

### Evidence

- In the client handler at `libclient.so` file VA `0x94d6b0`, the parser reads entity id, type,
  position, then four single-byte values. The first three bytes are sign-extended and multiplied by
  the constant at `0x2a24e4c` (`pi / 128`); the fourth is the flag. The handler constructs
  `CompressionIStream` at `0x98c3c8` (`0x94d80c` call site) over the remaining bytes.
- `CompressionIStream` at `0x98c3c8` reads one byte: `0` is pass-through, `1..9` and `10` select
  decompression implementations, and other values reach the invalid-compression error at the
  xrefs near `0x98c464` and `0x98c690` (string at `0x2a464b0`). This distinguishes the entity flag
  from the compression byte.
- `ClientApp::createEntity` at `0x91ded4` calls `EntityType::newDictionary` at `0x92e944` with mode
  3 for a non-player entity. Mode 3 reads a mask byte only when bytes remain; with no property bytes,
  it creates the default dictionary. In mode 3, mask bit `1` means use the `.def` default and read no
  value; bit `0` means decode the value from the stream. The exact old failure (`SequenceDataType:
  Invalid size -2147090432 (341 bytes remaining)`) is reproduced by the parser analysis in
  [CREATE_ENTITY_FORMAT.md](CREATE_ENTITY_FORMAT.md), section 3, using the former malformed
  `space` payload. The missing mask byte made `0xbc` (the low byte of little-endian map id 700) look
  like the mask flag and shifted the subsequent values.
- **Live Mercury capture (RO-056, 2026-11-26):** gateway log after
  `trigger_battle.txt` line `space`:

  ```text
  [BATTLE] trigger 'space' ->
  0b214e0000ff096000214e00000e00000000000000000000000000000000000001
  eeffffffffffff81f9feff0fbc02000001000000010000000040534400301ac5
  b0040000b00400000040534400301ac50040534400301ac52c01000001000000
  224e000064000000
  ```

  Parse of that hex (client message ids): `0b` enterAoI + eid `0x00004e21` (20001) + alias `0xff`;
  `09` createEntity var16 length `0x0060`; eid 20001; type `0x000e` (BattleGroundSpace); 12 zero
  position bytes; three direction bytes `00 00 00`; then property stream
  `00` flag, `00` compression, `01` mask flag, 12-byte mask `ee ff ff ff ff ff 81 f9 fe ff 0f`,
  then `mapID=700` (`bc 02 00 00`) and the other selected values. Source: `logs/server.log` lines
  around the `trigger 'space'` print (same session also logged
  `BattleGroundSpace(20001).notifyEnterWorld`).

## Which property list is used

`EntityType::newDictionary(mode 3)` reads the client description's `desc+0x88` property list. The
list builder at `0x9d0b54..0x9d0b94` selects properties whose flag has bit 1 set: `OTHER_CLIENTS`
and `ALL_CLIENTS`. They share one ordered list for non-player creation. `OWN_CLIENT`,
`CELL_PUBLIC`, `CELL_PUBLIC_AND_OWN`, and `BASE_AND_CLIENT` are not in this createEntity list.

The source order is the entity description's master parse order. `EntityDescription::parseProperties`
at `0x9d22d4` replaces a duplicate property in place: its first position is retained and its final
definition (including type and flags) wins. There is no alphabetical or detail-level sorting.
`BattleGroundSpace` therefore has 92 selected entries and `Plane` has 8. For example,
`BattleGroundSpace.circleStage` is at index 57 in this selected list, as recorded in
[CREATE_ENTITY_FORMAT.md](CREATE_ENTITY_FORMAT.md), section 4.

The initial failing payload provides a second consistency check: after the missing mask caused the
92-entry bit vector to be consumed from the wrong position, the decoder reached the same
`SequenceDataType` error and remaining-byte count as the recorded client log. The client trace in
`docs/LOBBY_FINDINGS.md`, update 9, then records successful `space` creation with `circleStage=1`
and the other transmitted circle fields.

## Emulator evidence already recorded

`docs/LOBBY_FINDINGS.md`, update 9, records that on a fresh emulator match:

- `space` created `BattleGroundSpace` entity 20001 and `plane` created entity 20002 without stream
  errors. `spacemap` with only `mapID` got past the previous `maps_utils` `None` failure, then failed
  later with `set_gameStatus` `KeyError: 0`; setting `gameStatus=1` worked.
- `client/frida/payloads/entities_state.py` read `Globals.spaceEntity` as the space entity,
  `circleStage=1`, the transmitted circle values, and entity 20002 as `Plane`.

The old malformed-message failure is documented in `docs/LOBBY_FINDINGS.md`, update 8: the client
stopped acknowledging and the gateway logged repeated `BASEAPP RESEND`. This is why malformed
payload experiments require a fresh match. Recreating `createEntity` for an entity id that is
already in AoI (without `leaveAoI` first) also produced a RESEND loop in the RO-056 resume session.

## RO-056 live verification (2026-11-26 resume)

**Result: acceptance criterion 3 runnable and passed for framing + entity readback.** Match entry
was restored by tapping START on a visible lobby (1630,970). `to_match.sh` alone is still fragile
when the UI is not on the main lobby (depot/workshop, popups). `compatibility_status` remains
`unknown` (not an original-server claim).

Environment: LDPlayer `emulator-5554`, adb `E:/LDPlayer/LDPlayer9/adb.exe`, gateway
`logs/server.log`, Frida `client/frida/payloads/framing/ro056_entities_check.py`.

| Step | Command / action | Outcome |
|---|---|---|
| Lobby | Screenshot showed START on main hall | OK |
| Enter match | adb tap `(1630,970)` on visible lobby | `createHallTeam` → `matchBattleGround` → `-> battle: resetEntities` |
| Enter match (RO-107 corroboration) | `bash tools/to_match.sh` ~318 s, `22:04:38` | Same hall chain on client UDP port `56690` without manual START tap |
| Auto space | `BATTLE_SPACE` `spacet` (~20 s) | `space entity (pre-start countdown) -> 109B`; `BattleGroundSpace(20001).notifyEnterWorld` |
| Frida (first match) | `bash tools/probe.sh …/framing/ro056_entities_check.py` | `ENT 20001 BattleGroundSpace`; `ent20001.circleStage=1`; `mapID=700`; corroboration in `framing/ro056_live_out.log` |
| First-match RESEND | Log window `21:50:55`–`21:52:00` after first space | **0** `BASEAPP RESEND` lines |
| Explicit `space` | `trigger_battle.txt` = `space` | Live hex above; second create without leave → orphan RESEND to dead peer `51892` seq=1504 |
| Clean recreate | `trigger_battle.txt` = `leave 20001` then `space` | `trigger 'leave 20001' -> 0f0400214e0000` then `trigger 'space' ->` (same layout hex) |
| Frida after leave+space | `…/framing/captures/ro056_entities_leave_space.log` | `Globals.spaceEntity` set; `ent20001.circleStage=1`; `PlayerBattleGroundAvatar` |

**RESEND note:** after a bad duplicate `createEntity` on eid 20001, the gateway kept logging
`BASEAPP RESEND seq=1504 ack=546` to UDP peer `('192.168.180.137', 51892)`. The later healthy match
used a different client port and still answered Frida. Two `ros_server.py` processes were observed
running at once; recommend the CTO keep a single gateway process so RESEND attribution stays clean.

**Match-entry note:** when already on the main lobby with START visible, one tap at `(1630,970)` is
enough. `tools/to_match.sh` restarts the game and assumes popup timing; if the client lands in
depot/workshop, START never fires. No gateway code change was required for this resume.

## Property updates and entity methods

See also `docs/ENTITY_PROPERTY_UPDATE_FORMAT.md` (static) and `server/extract/createentity_notes.json`
(RO-056 consolidated status).

| Direction and message | Result | Evidence / limit |
|---|---|---|
| ClientInterface message 10, `updateEntity` | **Unknown on this client** — not observed as the live update path. | `message_map.txt` names id 10; static analysis (`EntityMessageHandler` `0x94bbf0`) routes property changes through entity message ids `0xC0`–`0xFF`, not message 10. No hex capture of message 10 changing a property. |
| Server to client: `0xC0\|idx` (and `0xFD`+ path for idx ≥ 61) | **Verified for the own player (`BattleGroundAvatar`)**; **unknown for non-player entities** (Space, Plane, DtsProp). | Live: `LOBBY_FINDINGS` update 12 (`setp dtsWeapon4`, `wpn` equip). Static: `propertyEvent` `0x9644a4`, index = `desc+0x70` list (495 for avatar; 95 for space — not the 92-entry createEntity list). Not re-tested as a non-player update in RO-056. |
| Client to server: non-player exposed cell method `0x80\|idx` | **Verified** for requests on `BattleGroundSpace`: `openElement` `0x88`, `closeElement` `0x89`; `DtsProp.tryPickUp` `0x81`. | `docs/LOBBY_FINDINGS.md`, update 10. |
| Server to client: non-player client-method `0x80\|idx` | **Unknown** (layout assumed same id scheme as inbound; no outbound capture). | Door `onElementOpen` / `onElementClose` echo produced no client errors (update 11); byte layout not recorded. |

Do not assume the createEntity list (`desc+0x88`, 92 entries for `BattleGroundSpace`) is the
property-update index space (`desc+0x70`, 95 entries for the same type).

## Remaining issues

- Live-verify `0xC0|idx` property updates on `BattleGroundSpace`, `Plane`, and `DtsProp` (index space
  differs from createEntity).
- Capture server-to-client `0x80|idx` bytes on a non-player entity (door replies are error-free but
  uncaptured).
- Confirm whether ClientInterface message 10 is ever emitted on this build (static evidence says updates
  use `0xC0..0xFF` instead).
- Avoid sending a second `createEntity` for an eid still in AoI; use `leaveAoI` first (observed RESEND
  after duplicate `space` on 20001).
- Optional ops hardening (not RO-056 files_allowed): make `tools/to_match.sh` detect depot/workshop
  before START; ensure only one `ros_server.py` process.
- The `<implementedBy>` converters and some client-side value semantics remain caveats listed in
  [CREATE_ENTITY_FORMAT.md](CREATE_ENTITY_FORMAT.md), section 4; keep such values masked to defaults
  until separately verified.

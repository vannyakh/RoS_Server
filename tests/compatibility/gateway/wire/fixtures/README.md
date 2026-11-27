# Captured wire fixtures (RO-059)

Hex samples used by byte-level encoder tests. Sources are RO-056 live gateway
captures and documented offline builders — not original-server traces.

| File | Source |
|---|---|
| `space_create.hex` | `createentity_notes.json` `live_space_trigger_hex` / CREATE_ENTITY_FRAMING.md |
| `leave_aoi_20001.hex` | CREATE_ENTITY_FRAMING.md leave 20001 capture `0f0400214e0000` |
| `plane_create.hex` | Encoder output of verified layout for `plane` trigger (same framing as space) |
| `dtsprop_create.hex` | Encoder output for DtsProp eid 30000 propID 1001 at (10,20,30) |
| `robot_create_empty.hex` | Encoder output for Robot eid 40001 default dictionary |
| `prop_dtsCurWeapon.hex` | ENTITY_PROPERTY_UPDATE_FORMAT.md section 3 offline sample |
| `method_onElementOpen.hex` | Encoder output for BattleGroundSpace.onElementOpen(832, 1) |
| `method_showCircleNotify.hex` | Encoder output for BattleGroundSpace.showCircleNotify(1) |

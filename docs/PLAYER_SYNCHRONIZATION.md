# Player synchronization

**Entity lifecycle:** `create_entity` / `leave_aoi` (RO-059). Duplicate space without `leave_aoi` caused RESEND in historical captures.

**Properties:** `update_property` for hp, weapons, circle, pose. **Methods:** `entity_method` for client callbacks (`onPickUpPropEntity`, circle UI).

**Humans vs bots:** Same `PlayerRuntimeState`; bots use Robot entities (RO-069). Bot movement after spawn is static until 0x58 / nav research (RO-068, RO-111).

**Interest / AoI:** Per-address `MatchSession` today — not a single shared world for all players.

**Reconnect:** Mercury session re-auth; in-match state is gateway-local per connection.

See [PLAYER_PROTOCOL_MAPPING.md](PLAYER_PROTOCOL_MAPPING.md).
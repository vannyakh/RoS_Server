# Runtime migration plan

No new table is required for the authoritative loop. Positions, blockers, ammunition, and health stay in `WorldState`.

## Already in place

- `map_versions` and match `map_version_id` / `manifest_hash` pin a published map. The live tick does not load that package yet.
- `match_records` store a durable match separately from the in-memory match id. ADR-0008 keeps those ids apart.
- After each tick, finished results update kills and wins through `persistence_service`. Experience and currency are not granted.

## Not migrated

- Blockers are not SQL rows. A published map can later supply them from `map_objects` whose category is `collision`. The tick would copy those boxes into `Match.blockers` when the match starts.
- Gameplay configuration has no draft or publish table. `MatchRules` is the version a match retains.
- The loop is not a second operating-system process. Moving it out of the FastAPI process is an ADR change, not a schema change.
- UDP is not introduced. The WebSocket messages are the contract a future transport would carry.

## Safe order

1. Keep using `AuthoritativeSession` and the WebSocket actions for two players.
2. Load collision boxes from a published map version into the match at start.
3. Add a configuration version only when a match records the version id it started with.
4. Split the process only after a tick benchmark shows HTTP work delaying the 20 Hz loop.
5. Replace the Python simulator only with a new ADR and a client that still speaks `player.input` and `player.action`.

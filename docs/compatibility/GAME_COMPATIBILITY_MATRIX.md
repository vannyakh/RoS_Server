# Game compatibility matrix

Compatibility status describes comparison with authorized original Rules of Survival behavior.
A passing test of this server's own rules does not change `unknown` to `compatible`.
No authorized original specification is checked in. Every current row stays `unknown`.

## Measurements

- Tracked functions: 43
- Implementation coverage: 26 implemented, 10 partial, 7 not implemented
- Test coverage of those functions: 30 passing, 13 not run
- Original RoS compatibility: 0 compatible, 43 unknown

| feature_id | function_name | implementation_status | compatibility_status | test_status | priority | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| AUTH-001 | Account registration | implemented | unknown | passing | critical | tests/integration/test_auth.py |
| AUTH-002 | Login | implemented | unknown | passing | critical | tests/integration/test_auth.py |
| AUTH-003 | Session creation | implemented | unknown | not_run | high | none |
| AUTH-004 | Session expiration | implemented | unknown | passing | high | tests/compatibility/authentication/test_login.py |
| AUTH-005 | Logout | not_implemented | unknown | not_run | medium | none |
| AUTH-006 | Account validation | implemented | unknown | not_run | high | none |
| PLAY-001 | Player creation | implemented | unknown | passing | critical | tests/database/test_relationships.py |
| PLAY-002 | Player profile | implemented | unknown | passing | high | tests/compatibility/player/test_profile.py |
| PLAY-003 | Nickname | implemented | unknown | passing | medium | tests/compatibility/player/test_profile.py |
| PLAY-004 | Level | implemented | unknown | passing | medium | tests/compatibility/player/test_profile.py |
| PLAY-005 | Experience | partial | unknown | not_run | medium | none |
| PLAY-006 | Player statistics | implemented | unknown | passing | high | tests/integration/test_match.py |
| PLAY-007 | Progression | partial | unknown | not_run | low | none |
| LOB-001 | Lobby creation | partial | unknown | passing | high | tests/repositories/test_account_repository.py |
| LOB-002 | Lobby joining | partial | unknown | passing | high | tests/compatibility/lobby/test_lobby_rules.py |
| LOB-003 | Lobby leaving | partial | unknown | passing | medium | tests/unit/test_gameplay.py |
| LOB-004 | Player capacity | implemented | unknown | passing | high | tests/compatibility/lobby/test_lobby_rules.py |
| LOB-005 | Ready state | partial | unknown | passing | medium | tests/compatibility/lobby/test_lobby_rules.py |
| LOB-006 | Team creation | partial | unknown | passing | medium | tests/compatibility/lobby/test_lobby_rules.py |
| LOB-007 | Team membership | implemented | unknown | not_run | medium | none |
| MM-001 | Match request | implemented | unknown | passing | critical | tests/compatibility/matchmaking/test_queue.py |
| MM-002 | Match queue | implemented | unknown | passing | critical | tests/integration/test_match.py |
| MM-003 | Match creation | implemented | unknown | passing | critical | tests/unit/test_gameplay.py |
| MM-004 | Player allocation | implemented | unknown | passing | high | tests/unit/test_gameplay.py |
| MM-005 | Match cancellation | partial | unknown | passing | medium | tests/unit/test_gameplay.py |
| MM-006 | Match start | implemented | unknown | passing | critical | tests/compatibility/gameplay/test_scenario.py |
| GP-001 | Player state | implemented | unknown | passing | critical | tests/unit/test_engine.py |
| GP-002 | Movement | implemented | unknown | passing | critical | tests/compatibility/gameplay/test_scenario.py |
| GP-003 | Health | implemented | unknown | passing | high | tests/unit/test_gameplay.py |
| GP-004 | Damage | implemented | unknown | passing | high | tests/compatibility/weapons/test_shot.py |
| GP-005 | Weapon handling | implemented | unknown | passing | high | tests/compatibility/weapons/test_shot.py |
| GP-006 | Inventory | partial | unknown | passing | high | tests/compatibility/inventory/test_pickup.py |
| GP-007 | Equipment | not_implemented | unknown | not_run | low | none |
| GP-008 | Vehicles | not_implemented | unknown | not_run | low | none |
| GP-009 | Team state | not_implemented | unknown | not_run | medium | none |
| GP-010 | Match duration | partial | unknown | not_run | medium | none |
| GP-011 | Player elimination | implemented | unknown | passing | critical | tests/compatibility/gameplay/test_scenario.py |
| RS-001 | Match completion | implemented | unknown | passing | critical | tests/compatibility/match_results/test_results.py |
| RS-002 | Placement | implemented | unknown | passing | high | tests/compatibility/match_results/test_results.py |
| RS-003 | Kill statistics | implemented | unknown | passing | high | tests/compatibility/match_results/test_results.py |
| RS-004 | Experience rewards | not_implemented | unknown | not_run | medium | none |
| RS-005 | Currency rewards | not_implemented | unknown | not_run | medium | none |
| RS-006 | Player progression | not_implemented | unknown | not_run | low | none |

## Notes

- `AUTH-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: This server's username and password rules are independent.
- `AUTH-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: JWT is this server's session token, not an original client token.
- `AUTH-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: A SHA-256 token hash is stored. No test asserts the session row.
- `AUTH-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Expiration is the JWT exp claim.
- `AUTH-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: No logout route revokes AccountSession.
- `AUTH-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Active status is checked on HTTP and WebSocket. Suspended accounts are not covered by a test.
- `PLAY-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: One profile per account.
- `PLAY-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Profile id in the HTTP response is the account id.
- `PLAY-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Nickname is unique and defaults from the username.
- `PLAY-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Level starts at 1 and is not changed by a match.
- `PLAY-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The column exists. Matches do not grant experience.
- `PLAY-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Kills, wins, and matches are stored. Other original stat lines are unknown.
- `PLAY-007` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The table exists. Match completion does not write a progression row.
- `LOB-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Durable create exists in LobbyService. The HTTP route exposes the in-memory queue.
- `LOB-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Join rules are tested on the simulator and the service. There is no join HTTP route.
- `LOB-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Leave is implemented for the in-memory queue, not the durable lobby table.
- `LOB-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Capacity is a service check, not a single database constraint.
- `LOB-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The column and the simulator track ready. No service or route updates it.
- `LOB-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The simulator and the teams table exist. No HTTP route creates a team.
- `LOB-007` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: LobbyService.join_team enforces one team per lobby. No dedicated test calls it.
- `MM-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Queue is in memory. It is not an original matchmaking service.
- `MM-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Queue wait and bot fill are local settings.
- `MM-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Match ids are random UUIDs.
- `MM-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Empty slots can be filled with local bots.
- `MM-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: A queued player can leave. In-match forfeit is separate.
- `MM-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Start moves through countdown and drop using local timers.
- `GP-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: State is in memory and is not an original client snapshot.
- `GP-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Speed is 5 map units per second from app/game/rules.py.
- `GP-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Health starts at 100. Zone damage uses local rates.
- `GP-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Damage numbers are independent test values, not original weapon tables.
- `GP-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Pistol and rifle values live in app/game/items.py.
- `GP-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Match loot is in memory. Durable stacks are a separate table.
- `GP-007` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Equipment definitions can be stored. The match loop does not equip them.
- `GP-008` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: No vehicle simulation is implemented.
- `GP-009` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The live match is free-for-all. Lobby teams are not match teams.
- `GP-010` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Phase timers exist in MatchRules and are not asserted against a clock.
- `GP-011` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Elimination is health reaching 0 from shots or the zone.
- `RS-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The match phase becomes ended when one combatant remains.
- `RS-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Winner is place 1. Other places follow elimination order.
- `RS-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Kills count eliminations by shot in the in-memory match.
- `RS-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: No experience is granted at match end.
- `RS-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Currency tables exist. Match completion does not pay them.
- `RS-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Progression rows are not written from match results.

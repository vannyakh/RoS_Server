# Game compatibility matrix

Compatibility status describes comparison with authorized original Rules of Survival behavior.
A passing test of this server's own rules does not change `unknown` to `compatible`.
No authorized original specification is checked in. Every current row stays `unknown`.

## Measurements

- Tracked functions: 43
- Implementation coverage: 35 implemented, 3 partial, 5 not implemented
- Test coverage of those functions: 38 passing, 5 not run
- Original RoS compatibility: 0 compatible, 43 unknown

| feature_id | function_name | implementation_status | compatibility_status | test_status | priority | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| AUTH-001 | Account registration | implemented | unknown | passing | critical | tests/integration/test_auth.py |
| AUTH-002 | Login | implemented | unknown | passing | critical | tests/integration/test_auth.py |
| AUTH-003 | Session creation | implemented | unknown | passing | high | tests/integration/test_auth_session.py |
| AUTH-004 | Session expiration | implemented | unknown | passing | high | tests/compatibility/authentication/test_login.py |
| AUTH-005 | Logout | implemented | unknown | passing | medium | tests/integration/test_auth_session.py |
| AUTH-006 | Account validation | implemented | unknown | passing | high | tests/integration/test_auth_session.py |
| PLAY-001 | Player creation | implemented | unknown | passing | critical | tests/database/test_relationships.py |
| PLAY-002 | Player profile | implemented | unknown | passing | high | tests/compatibility/player/test_profile.py |
| PLAY-003 | Nickname | implemented | unknown | passing | medium | tests/integration/test_game_services.py |
| PLAY-004 | Level | implemented | unknown | passing | medium | tests/compatibility/player/test_profile.py |
| PLAY-005 | Experience | partial | unknown | not_run | medium | none |
| PLAY-006 | Player statistics | implemented | unknown | passing | high | tests/integration/test_match.py |
| PLAY-007 | Progression | partial | unknown | not_run | low | none |
| LOB-001 | Lobby creation | implemented | unknown | passing | high | tests/integration/test_lobby_routes.py |
| LOB-002 | Lobby joining | implemented | unknown | passing | high | tests/integration/test_lobby_routes.py |
| LOB-003 | Lobby leaving | implemented | unknown | passing | medium | tests/integration/test_lobby_routes.py |
| LOB-004 | Player capacity | implemented | unknown | passing | high | tests/compatibility/lobby/test_lobby_rules.py |
| LOB-005 | Ready state | implemented | unknown | passing | medium | tests/integration/test_lobby_routes.py |
| LOB-006 | Team creation | implemented | unknown | passing | medium | tests/integration/test_lobby_routes.py |
| LOB-007 | Team membership | implemented | unknown | passing | medium | tests/integration/test_core_services.py |
| MM-001 | Match request | implemented | unknown | passing | critical | tests/compatibility/matchmaking/test_queue.py |
| MM-002 | Match queue | implemented | unknown | passing | critical | tests/integration/test_match.py |
| MM-003 | Match creation | implemented | unknown | passing | critical | tests/unit/test_gameplay.py |
| MM-004 | Player allocation | implemented | unknown | passing | high | tests/unit/test_gameplay.py |
| MM-005 | Match cancellation | partial | unknown | passing | medium | tests/integration/test_core_services.py |
| MM-006 | Match start | implemented | unknown | passing | critical | tests/compatibility/gameplay/test_scenario.py |
| GP-001 | Player state | implemented | unknown | passing | critical | tests/unit/test_engine.py |
| GP-002 | Movement | implemented | unknown | passing | critical | tests/compatibility/gameplay/test_scenario.py |
| GP-003 | Health | implemented | unknown | passing | high | tests/unit/test_gameplay.py |
| GP-004 | Damage | implemented | unknown | passing | high | tests/compatibility/weapons/test_shot.py |
| GP-005 | Weapon handling | implemented | unknown | passing | high | tests/compatibility/weapons/test_shot.py |
| GP-006 | Inventory | implemented | unknown | passing | high | tests/integration/test_core_services.py |
| GP-007 | Equipment | not_implemented | unknown | not_run | low | none |
| GP-008 | Vehicles | implemented | unknown | passing | low | tests/unit/test_simulation.py |
| GP-009 | Team state | not_implemented | unknown | not_run | medium | none |
| GP-010 | Match duration | implemented | unknown | passing | medium | tests/unit/test_simulation.py |
| GP-011 | Player elimination | implemented | unknown | passing | critical | tests/compatibility/gameplay/test_scenario.py |
| RS-001 | Match completion | implemented | unknown | passing | critical | tests/compatibility/match_results/test_results.py |
| RS-002 | Placement | implemented | unknown | passing | high | tests/compatibility/match_results/test_results.py |
| RS-003 | Kill statistics | implemented | unknown | passing | high | tests/compatibility/match_results/test_results.py |
| RS-004 | Experience rewards | not_implemented | unknown | passing | medium | tests/integration/test_game_services.py |
| RS-005 | Currency rewards | not_implemented | unknown | passing | medium | tests/integration/test_game_services.py |
| RS-006 | Player progression | not_implemented | unknown | not_run | low | none |

## Notes

- `AUTH-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: This server's username and password rules are independent.
- `AUTH-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: JWT is this server's session token, not an original client token.
- `AUTH-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: A SHA-256 token hash is stored and checked on each authenticated request. Logout sets revoked_at.
- `AUTH-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: A request is rejected when the JWT exp has passed or the stored session expires_at has passed.
- `AUTH-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Logout revokes one stored session. Original Rules of Survival logout behavior is unknown.
- `AUTH-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Suspended and closed accounts still have no dedicated test. Original validation behavior is unknown.
- `PLAY-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: One profile per account.
- `PLAY-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Profile id in the HTTP response is the account id.
- `PLAY-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Nickname is unique, stored in lowercase, and can be changed by the authenticated player. Level and account username cannot.
- `PLAY-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Level starts at 1 and is not changed by a match.
- `PLAY-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The column exists. Matches do not grant experience.
- `PLAY-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Kills, wins, and matches are stored. Other original stat lines are unknown.
- `PLAY-007` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The table exists. Match completion does not write a progression row.
- `LOB-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: POST /api/v1/lobby creates a durable lobby. GET /api/v1/lobby still returns the in-memory queue.
- `LOB-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: POST /api/v1/lobby/{id}/members joins the authenticated player.
- `LOB-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The in-memory queue uses account ids. Durable membership uses player ids. The last member to leave closes the lobby. There is no leader column.
- `LOB-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Capacity is reserved with a conditional update of current_players. A player can still be a member of more than one lobby.
- `LOB-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: A missing member is rejected. Setting the same ready value again is accepted. Original ready behavior is unknown.
- `LOB-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: POST /api/v1/lobby/{id}/teams creates a team after the player has joined.
- `LOB-007` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: DELETE /api/v1/lobby/teams/{id}/members removes the team row only. Original team behavior is unknown.
- `MM-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Queue is in memory. It is not an original matchmaking service.
- `MM-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Queue wait and bot fill are local settings.
- `MM-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Match ids are random UUIDs.
- `MM-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Empty slots can be filled with local bots.
- `MM-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Stored cancel does not stop an in-memory match. Original cancellation is unknown.
- `MM-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Start moves through countdown and drop using local timers.
- `GP-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: State is in memory and is not an original client snapshot.
- `GP-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Speed is 5 map units per second from app/game/rules.py.
- `GP-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Health starts at 100. Zone damage uses local rates.
- `GP-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Damage numbers are independent test values, not original weapon tables.
- `GP-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Pistol and rifle values live in app/game/items.py.
- `GP-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Stored stacks use the development catalog. Match loot is separate. Original inventory is unknown.
- `GP-007` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Equipment definitions can be stored. The match loop does not equip them.
- `GP-008` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Speed 12 is a local value in app/game/items.py. Original vehicle behavior is unknown.
- `GP-009` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The live match is free-for-all. Lobby teams are not match teams.
- `GP-010` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The clock uses this server's timers. Original match duration is unknown.
- `GP-011` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Elimination is health reaching 0 from shots or the zone.
- `RS-001` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: The match phase becomes ended when one combatant remains.
- `RS-002` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Winner is place 1. Other places follow elimination order.
- `RS-003` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Kills count eliminations by shot in the in-memory match.
- `RS-004` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: No experience is granted at match end. A rewards object on a stored result is saved and not applied. Repeating finalization is rejected.
- `RS-005` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Currency tables exist. Match completion does not pay them, including when the result payload names a currency amount.
- `RS-006` original_reference: No authorized original Rules of Survival specification is in this repository. Known differences: Progression rows are not written from match results.

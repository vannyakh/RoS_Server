# API inventory

Read-only inventory of HTTP and WebSocket routes under `app/api` and `app/networking`, compared with services that have no route. This is this server's contract. It does not list original Rules of Survival endpoints.

Evidence labels: **Confirmed fact** (read in source), **Interpretation** (follows from those reads), **Hypothesis** (not executed), **Unknown** (not established here).

Mount point: `register_routes` in `app/api/router.py`.

## HTTP routes

| Method | Path | Handler | Auth | Calls | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | `app/api/v1/health.py` `health` | none | none | `{"status": "ok"}`, no `response_model` |
| GET | `/version.cfg` | `app/api/v1/health.py` `version_cfg` | none | `FileResponse` of `CONFIGURATIONS / "version.cfg"` | `text/plain` file |
| POST | `/api/v1/auth/register` | `auth.register` | none | `auth_service.register_player` | `PlayerCreated`, 201 |
| POST | `/api/v1/auth/login` | `auth.login` | none | `auth_service.login_player` | `TokenResponse` |
| GET | `/api/v1/players/me` | `players.me` | `current_account` | `player_service.profile_for_account` | `PlayerProfile` |
| GET | `/api/v1/lobby` | `lobby.lobby` | none | `lobby_status` → `game_engine.lobby_status` | dict, no `response_model` |
| POST | `/api/v1/lobby` | `lobby.open_lobby` | `current_player` | `LobbyService.open_lobby` | `LobbyResponse`, 201 |
| POST | `/api/v1/lobby/{lobby_id}/members` | `lobby.join_lobby` | `current_player` | `LobbyService.join` | `LobbyMemberResponse`, 201 |
| POST | `/api/v1/lobby/{lobby_id}/teams` | `lobby.open_team` | `current_player` | `LobbyService.create_team` | `TeamResponse`, 201 |
| POST | `/api/v1/lobby/teams/{team_id}/members` | `lobby.join_team` | `current_player` | `LobbyService.join_team` | `TeamMemberResponse`, 201 |
| GET | `/api/v1/matches` | `matches.matches` | none | `matchmaking_service.list_matches` | dict, no `response_model` |
| GET | `/api/v1/matches/{match_id}` | `matches.match_detail` | none | `matchmaking_service.get_match` | dict, or `HTTPException` 404 |
| GET | `/api/v1/items` | `items.items` | none | `GameDataService.list_items` | `Page[ItemDefinitionResponse]` |

**Confirmed fact.** Routers under `app/api/v1` contain no `select()` and no `commit()`. Services own the writes that exist.

**Confirmed fact.** `password_hash` and `token_hash` are absent from the response models used by these handlers (`PlayerCreated`, `TokenResponse`, `PlayerProfile`, lobby schemas, `ItemDefinitionResponse`). `AccountSessionResponse` in `app/schemas/account.py` includes `revoked_at` and omits `token_hash`. No route returns `AccountSessionResponse`.

**Confirmed fact.** `GET /api/v1/lobby` returns the in-memory queue view from `lobby_view`: `status` plus queued `player_id` and `waited`. It does not read the `lobbies` table. `GET /api/v1/matches` and `GET /api/v1/matches/{match_id}` read `game_engine` memory, not `MatchService`.

**Confirmed fact.** Bearer auth is `current_account` (JWT `sub`, `Account.status == "active"`) and `current_player` (that account's `Player` with `status == "active"`). Neither dependency loads `AccountSession`.

## WebSocket

**Confirmed fact.** One socket: `GET` upgrade `WS /api/v1/ws` in `app/networking/websocket.py`.

`ClientMessage` in `app/networking/protocol.py` accepts version `1` and these `type` values only:

| Client type | Handler | Effect |
| --- | --- | --- |
| `auth` | `_authenticate`, first message only | JWT in `payload.token`. Success sends `auth.ok` with `player_id`. A later `auth` returns `error` "Already authenticated" and stays open. |
| `heartbeat` | `_session_loop` | Echoes `heartbeat`. |
| `lobby.join` | `game_engine.join_queue` | Ack `lobby.join.ack`. In-memory queue. |
| `lobby.leave` | `game_engine.leave_queue` | Ack `lobby.leave.ack`. In-memory queue. |
| `match.forfeit` | `game_engine.forfeit` | Ack `match.forfeit.ack`. |
| `player.action` | `parse_action` then `game_engine.perform` | Actions: `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`. Ack `player.action.ack`. |
| `player.input` | `parse_input` then `game_engine.set_input` | Ack `player.input.ack` with `tick`. |

**Confirmed fact.** Close codes in this handler: `4001` auth timeout (5s), `1009` message over 4096 bytes, `4002` invalid auth JSON, `4003` missing or rejected auth, `4004` idle timeout (15s). After auth, invalid JSON stays on the socket as `error`. Sequence must increase. Rate limit is 20 messages per 1 second per connection.

**Confirmed fact.** `_player_id_for_token` decodes the JWT, loads `Account` by `sub`, and requires `status == "active"`. It returns `account.id`. `AccountService.login` calls `create_access_token(account.id)`, so `sub` is the account id. The socket does not load `Player` or `AccountSession`.

**Interpretation.** Durable HTTP lobby membership stores `Player.id` from `current_player`. The socket queue stores the account id. Those paths do not use the same identifier.

## Services with no route

| Service | Methods present | Route |
| --- | --- | --- |
| `auth_service.register_player` | wraps `AccountService.register` | `POST /api/v1/auth/register` |
| `auth_service.login_player` | rate limit, then `AccountService.login` | `POST /api/v1/auth/login` |
| `AccountService.register`, `login` | session row written on login | the two auth routes |
| `player_service.profile_for_account` | profile read | `GET /api/v1/players/me` |
| `lobby_status` | in-memory queue | `GET /api/v1/lobby` |
| `LobbyService.open_lobby`, `join`, `create_team`, `join_team` | durable rows | the four lobby `POST` routes |
| `GameDataService.list_items` | catalog page | `GET /api/v1/items` |
| `matchmaking_service.list_matches`, `get_match` | in-memory matches | the two match `GET` routes |
| `MatchService.create`, `transition`, `add_participant`, `finalize` | durable match rows | none |
| `InventoryService.add_item`, `remove_item`, `apply_currency` | durable stacks and currency | none |
| `PersistenceService.save_player_progress` | called from the tick in `app/main.py` | none |
| `AccountService` logout / revoke | method absent | none |
| `LobbyService` leave | method absent | none |
| `LobbyService` ready update | method absent | none |
| database readiness check | function absent from health | none |

**Confirmed fact.** `PlayerUpdate` exists in `app/schemas/player.py`. No player route accepts it. `RegisterRequest` has no `email` field. `AccountService.register` accepts `email`, and the register route does not pass one.

**Confirmed fact.** `LobbyRepository` exposes `by_id`, `member`, `member_count`, `team`, and `team_member`. It has no delete.

## Gaps called out for this audit

### Logout

**Confirmed fact.** Auth routes are register and login only. `AccountService` methods are `register`, `login`, and `_record`. `revoked_at` exists on `AccountSession` and on `AccountSessionResponse`. Login inserts `AccountSession` with `token_hash` and `expires_at`. No method in `account_service.py`, `auth_service.py`, `app/api`, or `app/networking` sets `revoked_at` or looks up `token_hash`.

**Interpretation.** A stored session hash is not consulted on later HTTP or WebSocket use. JWT expiry and `Account.status` are the checks that exist. Revoking a row would not, by the current handlers, reject a still-valid JWT.

**Unknown.** Original Rules of Survival logout behavior. No original endpoint is inferred.

### Durable lobby leave

**Confirmed fact.** `LobbyService` can open a lobby, add a member, create a team, and add a team member. It cannot remove a member. `WS` `lobby.leave` calls `game_engine.leave_queue`, which changes `WorldState` only.

**Interpretation.** A player who joined through `POST /api/v1/lobby/{lobby_id}/members` stays in `lobby_members` after a socket `lobby.leave`. The socket leave and the durable join are different stores.

**Confirmed fact.** `tools/game_simulator/runner.py` `SimulatedLobby.leave` removes an in-simulator member. That function is not wired to `LobbyService` or a route. `tests/compatibility/lobby/test_lobby_rules.py` exercises the simulator, not the HTTP leave path.

### Ready state

**Confirmed fact.** `lobby_members.ready` defaults to false (`app/models/lobby.py`). `LobbyMemberResponse.ready` is on the join response. `LobbyService.join` does not set `ready`. No HTTP path and no `ClientMessage.type` updates it. `app/game` has no ready field.

**Confirmed fact.** `SimulatedLobby.set_ready` exists and `test_lobby_capacity_ready_and_team_rules` calls it. That ready set is simulator state.

**Interpretation.** Members created by the HTTP join route are returned with `ready: false`, and nothing in the API or socket protocol can change that column.

**Unknown.** Original ready-check rules.

### Health database readiness

**Confirmed fact.** `GET /health` returns `{"status": "ok"}` and takes no `AsyncSession`. `GET /version.cfg` returns a local file. `app/api` and `app/networking` define no `/ready` route and no database probe.

**Hypothesis.** `GET /health` still returns 200 when the database is unreachable, because the handler never opens a session. This was not executed.

## Adjacent mounts (outside `app/api` and `app/networking`)

**Confirmed fact.** `app/main.py` can mount `StaticFiles` at `/play` when `ASSETS / "play"` is a directory. `app/observability/http.py` registers `GET /metrics`. Those are not part of the route trees requested above.

## Task report

```text
TASK ID:
unassigned project-audit (no tasks.json row was edited)
AGENT:
api-engineer
PHASE:
research
STATUS:
report written; registry unchanged

IMPLEMENTATION:
Read-only route inventory. No routes or services were edited.
FILES CREATED:
reports/project-audit/api.md
FILES MODIFIED:
none
DISCOVERIES:
HTTP surface is 13 routes plus WS /api/v1/ws.
Logout, durable lobby leave, ready updates, and a database health probe have no route.
MatchService, InventoryService, and PersistenceService.save_player_progress have no HTTP route.
Socket queue identity is the account id. Durable lobby membership uses Player.id.
DATABASE CHANGES:
none
API CHANGES:
none
GAME FUNCTION CHANGES:
none
TESTS EXECUTED:
none (read-only)
TEST RESULTS:
not run
COMPATIBILITY EVIDENCE:
No original Rules of Survival endpoint was claimed. Matrix notes that say lobby join or team create have no HTTP route disagree with app/api/v1/lobby.py as read for this report.
KNOWN ISSUES:
See gaps above.
RECOMMENDATION:
Leave implementation to a later assigned task. Do not treat this inventory as completion of AUTH-005 or lobby work.

OBJECTIVE:
Inventory routes and name service gaps for logout, durable lobby leave, ready state, and health database readiness.
IMPLEMENTATION SUMMARY:
One report file. Source was not changed.
SECURITY CONSIDERATIONS:
Login stores a token hash. Request auth does not read that hash or revoked_at. Hashes were not printed.
DEPENDENCIES:
None for this report. A logout implementation still needs the security and database reviews named on the existing AUTH-005 task text.
```

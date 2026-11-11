# API contract

This is the contract of this FastAPI server. It is not an original Rules of Survival protocol.

Confirmed fact. Paths below were read from `app/api/router.py`, `app/api/v1/`, and `app/networking/websocket.py`. Request and response names are the Pydantic models in `app/schemas/`. A route marked **added** was not present at the start of this session.

Two different lobby ideas share the `/api/v1/lobby` prefix:

- `GET /api/v1/lobby` reads the in-memory matchmaking queue.
- `POST /api/v1/lobby` and the `/{lobby_id}` routes read and write durable lobby rows.

WebSocket `player_id` is `accounts.id`. Durable lobby and match-record routes use `players.id`. `GET /api/v1/players/me` returns both: `id` is the account, `player_id` is the profile row.

## HTTP routes

| Method | Actual path | Request schema | Response schema | Authentication | Current behavior | Status |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | none | `{"status": "ok"}` | none | Process liveness only. Does not check the database. | existing |
| GET | `/ready` | none | `{"status", "database", "version"}` | none | Runs `SELECT 1`. Returns 503 `not_ready` when the database call fails. | existing |
| GET | `/version.cfg` | none | text file | none | Returns the local configuration file. | existing |
| GET | `/metrics` | none | Prometheus text | none | Process metrics. Player ids are not labels. Hidden from the OpenAPI schema. | existing |
| POST | `/api/v1/auth/register` | `RegisterRequest` | `PlayerCreated` | none | 201. Username is stored lowercase. Password is hashed. Creates an account, a player, and empty statistics. 409 if the username exists. 422 if the username or password fails validation. | existing |
| POST | `/api/v1/auth/login` | `LoginRequest` | `TokenResponse` | none | Checks the password, stores a SHA-256 hash of a new JWT, and returns the raw token once. Unknown user, wrong password, and a suspended or closed account all return 401 `Invalid username or password`. Five failures from one host in 60 seconds return 429. | existing |
| POST | `/api/v1/auth/logout` | none | empty | bearer session | 204. Sets `revoked_at` on that session only. A second logout with the same token returns 401. | existing |
| GET | `/api/v1/players/me` | none | `PlayerProfile` | bearer session | Account id, username, active flag, nickname, level, and kill/win/match totals. | existing |
| PATCH | `/api/v1/players/me` | `PlayerUpdate` | `PlayerProfile` | bearer session | Changes nickname and `avatar_id` only. Nickname is stored lowercase and must be unique. Level, experience, username, and statistics are unchanged. 409 if the nickname is taken. | added |
| GET | `/api/v1/lobby` | none | queue object | none | In-memory queue: `status` and `players`. This is not the durable lobby table. | existing |
| POST | `/api/v1/lobby` | `LobbyCreate` | `LobbyResponse` | bearer session | 201. Creates an open lobby. The creator is not a member until they join. 409 if `code` already exists. | existing |
| GET | `/api/v1/lobby/{lobby_id}` | none | `LobbyResponse` | bearer session, member | 404 if the lobby does not exist. 403 if the caller has not joined. | added |
| GET | `/api/v1/lobby/{lobby_id}/members` | none | `LobbyMemberResponse[]` | bearer session, member | Members ordered by `joined_at`. Same 404 and 403 rules as the detail route. | added |
| POST | `/api/v1/lobby/{lobby_id}/members` | none | `LobbyMemberResponse` | bearer session | 201. Joins the authenticated player. 404 if the lobby is missing. 409 if it is not open, the player is already a member, or it is full. The last free seat is reserved with a conditional update. | existing |
| DELETE | `/api/v1/lobby/{lobby_id}/members` | none | empty | bearer session | 204. Removes that player's lobby and team membership. 404 if they are not a member. The last member closes the lobby. | existing |
| POST | `/api/v1/lobby/{lobby_id}/ready` | `ReadyUpdate` | `LobbyMemberResponse` | bearer session, member | Sets `ready` true or false. 409 if the lobby is not open or the caller is not a member. | existing |
| POST | `/api/v1/lobby/{lobby_id}/teams` | `TeamCreate` | `TeamResponse` | bearer session, member | 201. 409 if the caller has not joined or the team code exists in that lobby. | existing |
| POST | `/api/v1/lobby/teams/{team_id}/members` | none | `TeamMemberResponse` | bearer session | 201. The player must already be in the lobby and cannot sit on two teams in that lobby. | existing |
| DELETE | `/api/v1/lobby/teams/{team_id}/members` | none | empty | bearer session | 204. Leaves the team and stays in the lobby. 404 if they are not on that team. | existing |
| GET | `/api/v1/matches` | none | live match list | none | In-memory matches only. Not `match-records`. | existing |
| GET | `/api/v1/matches/{match_id}` | none | one live match or 404 | none | In-memory snapshot. A stored match id returns 404 here. | existing |
| POST | `/api/v1/match-records` | `MatchRecordCreate` | `MatchRecordResponse` | bearer session | 201. Status starts at `scheduled`. 409 if `match_code` exists. | existing |
| POST | `/api/v1/match-records/{match_id}/participants` | none | empty | bearer session | 204. Adds the authenticated player. 409 if they are already in it, it is full, it is not `scheduled` or `lobby`, or they already have another `scheduled`, `lobby`, or `running` match. | existing |
| POST | `/api/v1/match-records/{match_id}/transition` | `MatchTransition` | `MatchRecordResponse` | bearer session, participant | `scheduled` to `lobby` or `cancelled`. `lobby` to `running` or `cancelled`. `running` to `cancelled`. Completion is not a transition. 403 for a non-participant. 409 for an illegal transition. | existing |
| POST | `/api/v1/match-records/{match_id}/results` | `MatchFinalize` | `MatchRecordResponse` | bearer session, participant | Completes a `running` match and stores placements. A second call returns 409. The `rewards` object is stored and is not applied to experience, currency, or statistics. | existing |
| GET | `/api/v1/items` | `limit`, `offset` query | `Page[ItemDefinitionResponse]` | none | Paged item catalog. | existing |
| GET | `/api/v1/inventory` | none | `InventoryResponse` | bearer session | The caller's stacks and currency balances. | existing |
| POST | `/api/v1/inventory/items` | `ItemQuantityChange` | `InventoryItemResponse` | bearer session | Adds quantity of a catalog item to the caller, up to `max_stack`. 404 if the code is unknown. | existing |
| POST | `/api/v1/inventory/items/remove` | `ItemQuantityChange` | `InventoryItemResponse` | bearer session | Decrements a stack the caller owns. 409 if the stack would go negative. | existing |
| POST | `/api/v1/inventory/currency` | `CurrencyChange` | `CurrencyResponse` | bearer session | Applies a non-zero amount to the caller's balance. 409 if the balance would go negative. | existing |
| WS | `/api/v1/ws` | first message is `auth` | see WebSocket events | session token in the first payload | The token is not accepted in the URL. | existing |

`/play` is a static browser client when `assets/play` exists. It is not a versioned API.

## Authentication details

Confirmed fact. `RegisterRequest` requires a username of 3–32 characters and a password of 12–128 characters. The service then accepts only `a-z`, `0-9`, and `_` after the username is lowercased.

Confirmed fact. `TokenResponse` is `access_token`, `token_type` (`bearer`), and `expires_in` seconds. The raw token is not stored. Later requests send `Authorization: Bearer <access_token>`.

Confirmed fact. A missing bearer header returns 401 `Not authenticated`. An expired JWT, a JWT with no session row, a revoked session, and a session whose `expires_at` has passed return 401 `Invalid or expired token`.

Confirmed fact. Passwords use `pwdlib` `PasswordHash.recommended()`. Session lookup loads the row by SHA-256 hash. Responses do not include `password_hash` or `token_hash`.

## Durable lobby rules

Confirmed fact. Lobby status is `open`, `starting`, or `closed`. New lobbies are `open`. Join and ready require `open`.

Confirmed fact. There is no leader column. Any member may create a team, set their own ready flag, and leave. The last member to leave sets the lobby to `closed` and sets `closed_at`. A closed lobby rejects new joins.

Confirmed fact. Membership is unique per lobby and player. Capacity is `max_players`. A player can currently belong to more than one lobby at the same time.

## Stored match states

Confirmed fact. Stored statuses are `scheduled`, `lobby`, `running`, `completed`, and `cancelled`. These names are this server's. They are not claimed as original protocol values.

Allowed transitions:

| From | To |
| --- | --- |
| `scheduled` | `lobby`, `cancelled` |
| `lobby` | `running`, `cancelled` |
| `running` | `completed` through `POST /results`, or `cancelled` through transition |
| `completed` | none |
| `cancelled` | none |

A player with `left_at` still null on a `scheduled`, `lobby`, or `running` match cannot join a second one. Completed and cancelled matches do not block a later match.

## WebSocket events

Every message is JSON with `version` 1, `type`, `sequence`, and `payload`. Client messages are limited to 4096 bytes. After auth, `sequence` must increase. More than 20 messages in one second receive `error` with `Rate limit exceeded`. The auth wait is 5 seconds. An idle connection is closed after 15 seconds.

| Event | Direction | Payload | Authentication | Authorization | Error behavior |
| --- | --- | --- | --- | --- | --- |
| `auth` | client to server | `token` | this message creates the session | token must match a live session | Any other first type closes with 4003. Bad JSON closes with 4002. Timeout closes with 4001. Invalid token sends `error` and closes with 4003. |
| `auth.ok` | server to client | `player_id` (account id) | session accepted | none beyond the session | Not sent when authentication fails. |
| `heartbeat` | both | empty object | required | none | Server echoes `heartbeat`. |
| `lobby.join` | client to server | empty | required | the connected account | Ack `lobby.join.ack` with `ok` and `detail`. A second join while queued returns success `Already queued`. A player already in a live match gets `ok: false`. |
| `lobby.leave` | client to server | empty | required | the connected account | Ack `lobby.leave.ack`. Leaving when not queued returns `ok: false`. |
| `player.input` | client to server | `move_x`, `move_y`, `aim_x`, `aim_y`, each from -1 to 1 | required | the connected account | Ack `player.input.ack` with `tick`. Invalid numbers send `error`. |
| `player.action` | client to server | `action`, optional `loot_id`, optional `item_id` | required | the connected account | Actions are `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`, `board`, `exit`. Ack `player.action.ack`. |
| `match.forfeit` | client to server | empty | required | the connected account must be in a live match | Ack `match.forfeit.ack`. |
| `state` | server to client | position, health, status, match id, aim, kills, map size, vehicle, and match details when in a match | connection already authenticated | sent only to that account's current socket | Sent by the tick. Not a client request. |
| `error` | server to client | `detail` | depends on the failure | none | Validation, sequence, and rate-limit failures stay on the socket. Authentication failures close it. |

Confirmed fact. A new socket for the same account replaces the previous one. The previous socket is closed with code 4000. Disconnect marks the in-memory player disconnected and removes a queued player from the queue.

Confirmed fact. `lobby.join` on the socket is the in-memory queue, not `POST /api/v1/lobby/{lobby_id}/members`.

## Map catalog

Confirmed fact. Map routes were added with the map content system. The public catalog lists published versions only. Drafts stay on the admin routes. Request and response fields, hashes, and error cases are in `docs/MAP_API_CONTRACT.md`.

| Method | Actual path | Authentication | Current behavior |
| --- | --- | --- | --- |
| GET | `/api/v1/maps` | none | Page of published maps. |
| GET | `/api/v1/maps/{map_id}` | none | Latest published detail, or 404. |
| GET | `/api/v1/maps/{map_id}/versions` | none | Published versions only. |
| GET | `/api/v1/maps/{map_id}/manifest` | none | Manifest with real SHA-256 file hashes. Optional `version`. |
| GET | `/api/v1/maps/{map_id}/assets/{asset_id}` | none | Published asset bytes. The response has no filesystem path. |
| POST | `/api/v1/admin/maps` | bearer, `MAP_PUBLISHERS` | 201 draft definition. |
| PATCH | `/api/v1/admin/maps/{map_id}` | bearer, `MAP_PUBLISHERS` | Draft metadata. Dimensions are rejected after a version is published. |
| POST | `/api/v1/admin/maps/{map_id}/versions` | bearer, `MAP_PUBLISHERS` | 201 draft version, regions, objects, spawns, and points of interest. |
| POST | `/api/v1/admin/maps/{map_id}/assets` | bearer, `MAP_PUBLISHERS` | Multipart asset registration. |
| POST | `/api/v1/admin/maps/{map_id}/publish` | bearer, `MAP_PUBLISHERS` | Validates stored bytes, then publishes. |
| POST | `/api/v1/admin/maps/{map_id}/pin` | bearer, `MAP_PUBLISHERS` | 204. Stores the exact version and manifest hash on a match. |

## Not implemented

Confirmed fact. These were requested by the game-services plan and are not routes:

- No leader role and no leader-transfer route.
- No durable equipment slots. `equip` is an in-memory match action.
- No HTTP matchmaking queue separate from the WebSocket. No Redis queue.
- No experience, currency, or inventory payout from match completion.
- No original client packet format.

Unknown. Original Rules of Survival authentication, lobby, matchmaking, and reward behavior.

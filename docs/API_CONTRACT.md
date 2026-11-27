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
| GET | `/api/v1/players/me` | none | `PlayerProfile` | bearer session | Account id, username, active flag, nickname, level, kill/win/match totals, `coin`, `diamond`, `equipped_skin`, and `owned_skins`. | existing |
| GET | `/api/v1/cosmetics/wallet` | none | `WalletResponse` | bearer session | Coin, diamond, equipped skin, and owned skin codes. A new account starts with 500 coin, 20 diamond, and the `recruit` skin. | added |
| GET | `/api/v1/cosmetics/skins` | none | `SkinResponse[]` | bearer session | Independent catalog: `recruit` (free), `field_jacket` (200 coin), `night_ops` (15 diamond). | added |
| POST | `/api/v1/cosmetics/skins/{code}/purchase` | none | `WalletResponse` | bearer session | Buys one skin and subtracts the price. 404 unknown code. 409 already owned or insufficient balance. | added |
| POST | `/api/v1/cosmetics/skins/{code}/equip` | none | `WalletResponse` | bearer session | Sets the equipped skin. 409 if that skin is not owned. 404 unknown code. | added |
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
| `lobby.join` | client to server | empty, or `mode` `training` for the practice range | required | the connected account | Ack `lobby.join.ack` with `ok` and `detail`. A second join while queued returns success `Already queued`. A player already in a live match gets `ok: false`. |
| `lobby.leave` | client to server | empty | required | the connected account | Ack `lobby.leave.ack`. Leaving when not queued returns `ok: false`. |
| `player.input` | client to server | `move_x`, `move_y`, `aim_x`, `aim_y`, each from -1 to 1 | required | the connected account | Ack `player.input.ack` with `tick`. Invalid numbers send `error`. |
| `player.action` | client to server | `action`, optional `loot_id`, optional `item_id` | required | the connected account | Actions are `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, `discard`, `board`, `exit`, `revive`, `attach`. Ack `player.action.ack`. |
| `match.forfeit` | client to server | empty | required | the connected account must be in a live match | Ack `match.forfeit.ack`. |
| `state` | server to client | position, health, status, match id, aim, kills, map size, vehicle, worn gear levels, and match details when in a match (loot `crate_id`, self gear/stats, end-of-match `results`; see `docs/NETWORK_PROTOCOL.md`) | connection already authenticated | sent only to that account's current socket | Sent by the tick. Not a client request. |
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

## Original-client gateway accounts

`bigworld_gateway/` calls these routes. They need the header `X-Gateway-Key` equal to `GATEWAY_API_KEY`. When `GATEWAY_API_KEY` is empty they answer 404. A wrong or missing key answers 401.

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| POST | `/api/v1/gateway/accounts/resolve` | `external_uid`, optional `ip_address` | Finds or creates the account for that uid and records a login. |
| PUT | `/api/v1/gateway/accounts/{external_uid}/character` | `nickname`, `char_type` | Sets the player nickname and the original-client career type. 409 if the nickname is taken, 404 for an unknown uid. |

Both return `account_id`, `username`, `status`, `can_play`, `is_new`, `nickname`, `char_type`. The first resolve creates account `gw_<uid>` with a player profile, statistics and starter items. That account has no usable password. `is_new` is true until a character is set. `can_play` is false when an operator suspended or banned the account; the gateway then sends no login reply. The uid comes from the Mercury login name (`<uid>@...`). The gateway derives that uid per device from the `ci=` device id the client sends on every SDK request (a 10-digit number from 9000000000 to 9999999999), so each device gets its own account. `CBP_GID` pins one uid for all devices and `DEVICE_UIDS=off` restores the shared uid `9000000001`.

### Gold and the Depot Workshop

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| POST | `/api/v1/gateway/accounts/{external_uid}/purchase` | `price` (0–1000000 diamonds), `props` (prop ids), `reason`, optional `request_id` | `yuanbao`, `added`, `recent_got`, and `replayed` only when `request_id` was sent. 409 `Insufficient balance`; 409 `request_id_reused`. |
| GET | `/api/v1/gateway/accounts/{external_uid}/state` | none | `yuanbao`, `items` (`prop_id`, `number`; rows with `number` 0 are left out), `outfit`, `head_frame`, `currencies`. |
| POST | `/api/v1/gateway/accounts/{external_uid}/workshop/compound` | `request_id`, `require`, `consume`, `consume_currency`, `add`, `reason` | `items`, `currencies`, `replayed`. 409 when the player lacks an item or gold; 422 for a currency other than 1. |
| POST | `/api/v1/gateway/accounts/{external_uid}/dev/grant` | `props`, `currencies` | The state view above. 404 unless `APP_ENV=development`. |

`currencies` is keyed by the original client's currency id as a string. Only `"1"` (gold coins, `const.MallCurrencyType.GP`) is stored: a `player_currencies` row with `currency_code` `gold`, next to the diamonds (`yuanbao`). A player without a gold row gets one on the first state read, compound or grant, with `GATEWAY_START_GOLD` (default 10000) and a `gateway:start` ledger row, in the same transaction.

Purchase idempotency: `request_id` is optional (8–64 characters of `A-Z a-z 0-9 _ -`; anything else is 422). Without it the route behaves as before: every call charges and grants, and the response has no `replayed` key. With it, an applied purchase writes exactly one diamond (`yuanbao`) `currency_transactions` row: `amount` is minus `price` (0 for a free draw, so a free draw is recorded too), `reason` `gateway:<reason>`, `note` `purchase:<request_id>`, `metadata` `{"request_id", "price", "props", "result"}`. A repeat with the same `request_id` for the same player and the same `price` and `props` (same order) changes nothing and returns the stored result with `replayed: true` (the `yuanbao` is the balance right after the first call). The same `request_id` with a different `price` or `props` answers 409 `{"detail": {"code": "request_id_reused", "message": ...}}` and changes nothing; `reason` is not compared. A refused purchase (409 `Insufficient balance`) stores nothing, so the same `request_id` can be retried after a top-up. Request ids are scoped per player. There is no unique index on the note: requests with a `request_id` are serialised by an in-process lock per player, which holds because the API runs as one process; two API processes on one database could still apply the same id twice.

Workshop compound body: `request_id` (1–64 characters of `A-Z a-z 0-9 _ -`), `require`, `consume` and `add` (each a list of `{"prop_id": int >= 0, "number": int >= 1}`, at most 50), `consume_currency` (a list of `{"currency_id": 1, "amount": int >= 0}`) and `reason` (1–64 characters of `a-z 0-9 _ . : -`, as for purchase). The gateway validates the recipe against the client's Workshop rules; RoS_Server applies it in one transaction. It checks that the player owns at least `number` of every `require` and every `consume` prop (each list is checked on its own; repeated prop ids are summed) and at least `amount` gold. If anything is short the answer is 409 with `{"detail": {"code": "insufficient", "missing": [...]}}` and nothing changes. A `missing` entry is `{"kind": "require" | "consume", "prop_id", "need", "have"}` or `{"kind": "currency", "currency_id": 1, "need", "have"}`. Otherwise the consumed counts and the gold are taken with conditional updates (a count never goes below zero), the `add` props are created or increased, and the answer is `{"items": [{"prop_id", "number"}], "currencies": {"1": gold}, "replayed": false}`, where `items` holds the current count of every prop the request named. A count can reach 0; the row is kept and `GET .../state` leaves it out, and a later purchase of that prop reports it in `added` again.

Idempotency: each applied compound writes one gold `currency_transactions` row (`amount` is minus the gold spent, possibly 0; `reason` `gateway:workshop:<reason>`; `note` `workshop:<request_id>`; `metadata` holds the recipe and the result). A second compound with the same `request_id` for the same player changes nothing and returns the stored result with `replayed: true`, even if its body differs. A refused (409) request stores nothing, so its `request_id` can be retried. There is no unique index on the note, so two identical requests sent at the same instant are not guarded against; the gateway sends one compound per player at a time.

Development grant body: `props` (list of `{"prop_id", "number" >= 1}`) and `currencies` (list of `{"currency_id": 1, "amount" >= 0}`). It adds the props and gold (ledger reason `gateway:dev_grant`) and returns the state view. It answers 404 unless `APP_ENV` is `development`. `scripts/dev_grant.py <external_uid> --prop 142091:2 [--prop id:n ...] [--gold 5000]` calls it with `GATEWAY_API_KEY` and `ROS_API_URL` from the environment or `.env`.

`bigworld_gateway/server/account_link.py` calls these as `get_state()`, `workshop_compound(request_id, require, consume, consume_currency, add, reason)`, `dev_grant(props, currencies)` and `record_match(report)`. A refused call returns `{"_error": <status>, "detail": <the server's detail>}`.

**Match report (gateway client).** When a match ends, the gateway may call `record_match` once with a `GatewayMatchReport` body. The POST path has no match id; a duplicate call counts a second match. On failure (`None` or `_error`), the gateway logs and continues — it does not retry automatically (RO-071 wires the call from `battle/modules/results.py`). Idempotent match reporting needs a separate API change (not this route).

### Player profile (My Page, Stats, Credit)

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| PUT | `/api/v1/gateway/accounts/{external_uid}/head-frame` | `{"head_frame": int >= 0}` | The account view with `head_frame`. The id is an original-client HeadFrameAppearanceType prop id; 0 means no frame. `GET .../state` and `.../profile` also return `head_frame`, and the gateway sends it to the client as Athlete `headFrameTag`. `GET .../profile` also returns `rank_tier` (bronze to king, score steps are this project's own design), `rank_logo_url`, `lobby_theme` and `lobby_background_url`: store paths from the asset library (kinds `rank`, keyed by tier, and `background`, keyed by the lobby theme prop id), empty when nothing was uploaded. The admin player detail `gateway` object carries the same fields, and `PATCH /api/v1/admin/players/{id}/profile` accepts `outfit.theme` to set the lobby background (kept when omitted; `GET .../state` returns it in `outfit.theme`). |
| GET | `/api/v1/gateway/accounts/{external_uid}/profile` | none | `nickname`, `level`, `char_type`, `portrait`, `rank_score`, `space_likes`, `current_season`, `credit`, `records`. |
| POST | `/api/v1/gateway/accounts/{external_uid}/matches` | `placement` (1–200), optional `season`, `queue` (`total`, `ranked`, `matching`), `team_mode` (`solo`, `dual`, `quad`, `five`), `kills`, `deaths`, `assists`, `damage`, `head_shots`, `hits`, `fires`, `fight_time_seconds`, `collect_count`, `heal_count`, `kill_distance_dm`, `move_distance_dm`, `rank_score_delta` | Adds one finished match and returns the profile. |
| POST | `/api/v1/gateway/accounts/{external_uid}/credit/claim` | none | `awards` (prop ids granted once, then cleared) and `credit`. |
| POST | `/api/v1/gateway/accounts/{external_uid}/presence` | `online` (bool) | `online`: whether the account now counts as online. `true` renews a 75-second lease, `false` ends it. 404 for an unknown uid. |
| GET | `/api/v1/gateway/store/listings` | none | `{"listings": [{"item_id", "goods_id", "on_sale", "currency", "price"}]}`: operator store-listing overrides (see "Lobby theme store listings"). |

`records` rows are keyed by `season` (0 = all time), `queue` and `team_mode` (`overall` plus the four sizes). Each row holds `fight_count`, `win_count`, `top5_count`, `kill_count`, `death_count`, `assist_count`, `damage`, `head_shot_count`, `hit_count`, `fire_count`, `fight_time_seconds`, `collect_count`, `heal_count`, and per-match maxima `max_round_kill`, `max_round_assist`, `max_round_heal`, `max_kill_distance_dm`, `max_move_distance_dm`, `max_fight_time_seconds`. Distances are decimetres, the unit the client divides for display. A match adds to its own mode and to `overall`, for its season (default `GATEWAY_CURRENT_SEASON`) and for season 0, and also to the web profile's `PlayerStatistics`. `placement` 1 counts a win and 1–5 a top-five finish. `rank_score_delta` moves `rank_score`, floored at 0.

`credit` is `score` (starts at 100), `status_last_week` (0 none, 1 silver, 2 gold, 3 diamond), `weeks` (consecutive authenticated weeks), `gifts` (unclaimed weekly reward prop ids) and `records` (latest 20 changes: `delta`, `reason`, `score_after`, `note`, `created_at`). The gateway turns this profile into the client's `onGetRecordData`, `onGetBaseInfo`, `queryPersonalInfoCB`, `queryCreditScoreCB` and `syncCreditStatus` replies (`bigworld_gateway/server/profile_screens.py`).

Operators manage these accounts through the admin routes. `GET /api/v1/admin/players` rows include `nickname`, `client` (`game` or `web`), `game_id` (the gateway `external_uid`, null for web), `rank_score`, `game_last_login_at` (both null for web) `online` (game socket or gateway presence lease) and `last_session` (newest successful login, or null), and the search matches nicknames. `GET /api/v1/admin/players/{account_id}` includes `gateway` (`external_uid`, `char_type`, `last_login_at`, `last_ip`), or null for web accounts. `PATCH /api/v1/admin/players/{account_id}/profile` with `nickname`, `char_type` (game-client accounts only) and a required `reason` needs `players.manage`, is written to the audit log, and reaches the game on its next login.

Login sessions: every web login (`POST /api/v1/auth/login`) and every gateway resolve writes a `login_history` row with `source` (`web` or `game`), `ip_address`, `country`, and for the game client the `device` the gateway sent with the resolve (`model`, `os_name`, `client_version`, `time_zone`, `language`, all optional), or for web the `User-Agent` (256 characters). The gateway takes the device from the client's SDK requests: the User-Agent `NeteaseMobileGame/a<sdk> (<model>;<android api level>)` and the query's `gv`, `time_zone` and `lang`. `country` is an ISO 3166 alpha-2 code looked up at login time in the offline database at `GEOIP_DB_PATH` (an `.mmdb` country file, such as DB-IP IP to Country Lite, read with the `maxminddb` package); no IP is sent elsewhere. It is null for private addresses, without a database, or when the IP is not listed. Admin session rows carry `id`, `created_at`, `status`, `source`, `ip_address`, `network` (`public`, `private` or null), `country`, `device_model`, `os_name`, `client_version`, `time_zone`, `language` and `user_agent`; the player detail lists the latest 20 as `sessions`.

The player detail also carries `online` (the account holds an open game socket on this server) and, in `gateway`, `props` (`prop_id`, `number`), `rank_score`, `credit_score`, `credit_status_last_week`, `credit_weeks`, `space_likes`, `national_flag` (the game's flag code, upper case, "" when unset), `current_season` and `records` (the battle record rows of `GET /api/v1/gateway/accounts/{external_uid}/profile`; season 0 is all-time). Zero-count inventory rows and props are left out.

`PATCH /api/v1/admin/players/{account_id}/profile` accepts one audited edit with a required `reason`. Each field group needs its own permission:

| Fields | Permission | Accounts |
| --- | --- | --- |
| `nickname` | `players.manage` | all |
| `level` (1–1000), `experience` (≥ 0) | `players.progress` | all |
| `char_type`, `outfit` (`body`, `wear`: prop id lists, 32 each at most) | `players.progress` | game client only |
| `rank_score` (≥ 0), `credit_score` (0–160) | `players.economy` | game client only |
| `national_flag` (0–8 letters, stored upper case, "" clears) | `players.manage` | game client only |

A credit change also writes a `gateway_credit_records` row with `reason` -1 and the operator's reason as `note`. An unchanged edit returns 422. The response is the updated player detail.

`POST /api/v1/admin/players/{account_id}/adjustments` with `kind` (`currency`, `item`, `prop`), `key` (lowercase currency code, item definition id, or original-client prop id), a non-zero `delta` and a required `reason` needs `players.economy`. A balance or count never goes below zero (409); rows are kept at zero, not deleted. A currency change writes a `currency_transactions` row with `reason` `admin_adjust`. Every adjustment is audited as `player.currency`, `player.item` or `player.prop`. The response is the updated player detail.

### Dashboard analytics

`GET /api/v1/admin/analytics` (needs `dashboard.read`) takes either `days` (1–366, the last N UTC days ending today; default 14) or `start` and `end` (UTC dates, both inclusive, at most 366 days; both are required). The response echoes `start`, `end` and `days`, and counts stored rows per UTC day: `daily` (`date`, `registrations_web`, `registrations_game`, `logins`, `failed_logins`, `active_players` = distinct accounts with a successful login, `matches`, `cases`, `reports`), `hourly_logins` (`[weekday 0=Monday, hour UTC, count]`), `countries` (top 10 `code`/`count`), `private_logins`, `devices` (top 8 by device model; web logins count as "Web browser"), `systems`, `sources`, `statuses` (all accounts), `levels` (players per level band), `totals` (sums of `PlayerStatistics`) and `top_players` (top 5 by kills). Nothing is sampled or estimated.

### Store administration

Reads need `store.read`; writes need `players.economy`; writes are audited and announced on the operator live feed as `player.changed`.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/v1/admin/store/ledger?start=&end=&currency=&kind=&q=&limit=&offset=` | Page of `currency_transactions` rows with the player: `id`, `created_at`, `account_id`, `player_id`, `nickname`, `currency`, `amount` (negative is spend), `balance_after`, `reason`, `kind` (`purchase`, `draw`, `topup`, `refund`, `grant`, `admin`), `item` (`mall <goods> ×<n>`, `draw pool <n>`, `skin <code>` or null), `note`, `refunded`. Default range is the last 30 UTC days. |
| GET | `/api/v1/admin/store/summary?start=&end=` or `?days=` | `spent` per currency, `credited` (`topup:<code>`, `refund:<code>`), `purchases`, `buyers`, `by_kind`, `daily` spend per currency, `top_items` and `top_spenders` (top 10). |
| GET | `/api/v1/admin/store/catalog` | The web skin catalog with `code`, `name`, `currency`, `price` and `sold` (counted from purchases that record the skin, from this change on). |
| GET | `/api/v1/admin/store/currencies` | Any signed-in operator. Currencies an operator can grant, top up or price in: `code`, `label`, `client_id` (the original client's MallCurrencyType, or null), `scope` (`web` for `coin` and `diamond`, `game` for the original client's currencies such as `gold` and `yuanbao`) and `spendable` (charged by a purchase route today; in-game purchases charge only `yuanbao`). |
| POST | `/api/v1/admin/store/topup` with `account_id`, `currency`, `amount` (> 0), `reference` (1–40 characters) and `reason` | 201 and the new ledger row (`reason` `topup:<reference>`). A reference is credited once per currency (409 on a repeat). No payment is taken. |
| POST | `/api/v1/admin/store/refund` with `transaction_id` and `reason` | 201 and the credit row (`reason` `refund:<transaction id>`). Only a purchase or draw that spent currency, once (409 on a repeat, 422 otherwise). Items already granted are not taken back. |

Web skin purchases now store `{"skin": <code>}` in the ledger row's details.

### Game servers (original client)

Each original-client gateway process reports itself; the game's server-select screen and the admin Game servers page read the same rows (`gateway_servers`).

| Method | Path | Body / query | Response |
| --- | --- | --- | --- |
| POST | `/api/v1/gateway/servers/heartbeat` | Gateway key. `server_key` (`^[a-z0-9][a-z0-9_-]{0,31}$`), `name` (`^[A-Za-z0-9_.-]{1,32}$`, used only on first registration), `host`, `port` (1–65535), `version`, `players_online`, `players_in_match`, optional `started_at` | `{"server_key", "name", "host", "port", "zone", "group_id", "status", "listed"}`. `status` is the effective state: the operator's value, or for `auto` `maintenance` when no heartbeat for 30 s, else `full` at ≥95 % of capacity, `busy` at ≥60 %, else `smooth`. 422 for a name with spaces or a bad field. |
| GET | `/api/v1/gateway/servers` | Gateway key | `{"servers": [entry]}`: listed servers only, by zone then key. The gateway builds `server_list_ad.txt` from it. |
| GET | `/api/v1/admin/game-servers` | `servers.read` | `{"servers": [entry + configured_status, capacity, version, live, players_online, players_in_match, started_at, last_seen_at], "players_online", "players_in_match"}`. Counts are 0 for a server that is not live. |
| PATCH | `/api/v1/admin/game-servers/{server_key}` | `servers.manage`. Any of `name`, `status` (`auto`, `smooth`, `busy`, `full`, `maintenance`), `capacity` (1–100000), `listed`, `zone`, plus `reason` (3–240) | The updated admin row. Audited as `server.update`. 404 unknown key. |

Metrics: `ros_gateway_servers_live`, `ros_gateway_players_online`, `ros_gateway_players_in_match`.

### System mail (original client)

Operators send mail to original-client players; the gateway serves it to the client's mail screen (`UISystemMail`, see `bigworld_gateway/docs/MAIL_FINDINGS.md`). Rows are `gateway_mails` (revision `9e9814d7f549`). `mail_id` is the client's INT32 mailID: a sequence per gateway identity that starts at 1.

Gateway routes need `X-Gateway-Key`. An unknown `external_uid` is 404.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/v1/gateway/accounts/{external_uid}/mails` | `{"mails": [MailView]}`, newest first. Deleted mail and mail past its deadline are left out. |
| GET | `/api/v1/gateway/accounts/{external_uid}/mails/{mail_id}` | MailView plus `content`, and marks the mail read. 404 when missing, deleted or expired. |
| POST | `/api/v1/gateway/accounts/{external_uid}/mails/{mail_id}/claim` | `{"props": [{"prop_id", "number"}], "gold", "items": [{"prop_id", "number"}], "currencies": {"1": gold}, "replayed"}`. 404 when missing, deleted or expired. |
| DELETE | `/api/v1/gateway/accounts/{external_uid}/mails/{mail_id}` | 204. Soft delete (`deleted_at`). 404 when missing, already deleted or expired. |

MailView is `mail_id`, `type` (client `SysMailTypeEnum`: 1 PROPS when the mail has attachments or gold, else 0 TXT), `title`, `sender`, `abstract` (first 40 characters of the content), `sent_at` (unix seconds), `deadline` (unix seconds, 0 for none), `unread` (bool), `claimed` (bool), `attachments` (`[{"prop_id", "number"}]`, at most 6) and `gold`.

A claim runs in one transaction: a conditional `UPDATE ... WHERE claimed_at IS NULL` sets `claimed_at` (and `read_at` if unset); only when that update hits the row are the attachments added to `gateway_items` (created or increased) and the gold added to the `gold` `player_currencies` row (client currency 1), with one `currency_transactions` row, `reason` `gateway:mail:<mail_id>`, when gold > 0. Attachment props are also put at the front of the Depot Recent list. A claim of a mail that was already claimed adds nothing and returns the mail's `props` and `gold` with the current counts and `replayed: true`, so two concurrent claims cannot both add. `items` is the current count of every attached prop and `currencies` the current gold balance. Deleting a mail that was not claimed forfeits its attachments and gold; operators can see such rows in the admin list.

Operator routes (same bearer auth as the store administration routes):

| Method | Path | Result |
| --- | --- | --- |
| POST | `/api/v1/admin/mails` | Needs `players.economy`. Body `account_ids` (1–200 RoS_Server account ids), `title` (1–64), `content` (0–2000, default ""), `sender` (1–32, default `System`), `attachments` (at most 6 `{"prop_id": int >= 0, "number": 1..999}`), `gold` (0–10,000,000), `deadline_days` (1–365, default 30), `reason` (3–240). 201 `{"sent": [{"account_id", "mail_id"}], "skipped": [account_id]}`: one mail per account with a gateway identity; accounts without one (web accounts, unknown ids) are skipped. Repeated ids are sent once. Each sent mail is audited as `player.mail` and announced on the live feed as `player.changed` with `change` `mail`. 422 for more than 6 attachments or an out-of-range field. |
| GET | `/api/v1/admin/mails?account_id=` | Needs `players.read`. `{"mails": [...]}`, newest first, every mail of that account including claimed, deleted and expired: MailView plus `content`, `account_id`, `deleted`, `expired`, `sent_by`, `read_at`, `claimed_at`, `deleted_at`. Empty for an account without a gateway identity. |
| POST | `/api/v1/admin/players/{account_id}/mail` | Support-page form for one player. Needs `players.economy`. Body `title`, `sender` (default `RoS Server`), `content` (required), `props` (list of `[prop_id, count]`), `deadline_days` (0 = longest allowed, 365), `reason` (3–240). The mail goes into the same game mailbox as `POST /api/v1/admin/mails`, so the client lists and claims it through the `/mails` routes above. 201 `{"id", "type", "title", "sender", "content", "props", "sent_at", "deadline", "claimed"}`, where `id` is the player's game `mail_id`. 404 unknown account; 422 for a web account without a gateway identity, or a mail that breaks the game mailbox limits (title over 64, sender over 32 characters, more than 6 props). |
| GET | `/api/v1/admin/players/{account_id}/mail` | Needs `players.read`. That player's game mail, newest first, in the same shape as the POST answer. |

`bigworld_gateway/server/account_link.py` calls the gateway routes as `list_mails()` (list of MailView, or None when not linked/down), `mail_detail(mail_id)` (detail dict, `{"_error": 404, "detail": ...}`, or None), `claim_mail(mail_id)` (claim body, `{"_error": <status>, ...}`, or None) and `delete_mail(mail_id)` (True when deleted, else False). A 204 answer reaches `_call` as `{}`.

### Weapon balance

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/api/v1/admin/weapons` | `weapons.read` | Every weapon, ordered by class and code: `code`, `name`, `weapon_class` (`assault`, `smg`, `sniper`, `shotgun`, `pistol`, `melee`), `damage`, `fire_rate` (rounds per minute), `magazine`, `reload_seconds`, `effective_range`, `max_range`, `falloff_percent`, `spread`, `recoil`, `head_multiplier`, `torso_multiplier`, `limb_multiplier`, `vehicle_damage`, `revision`, `updated_at`. |
| PUT | `/api/v1/admin/weapons/{code}` | `weapons.manage` | Creates or updates the weapon (`code` is 1-32 lowercase letters, digits or underscores). The body holds the fields above, plus optional `expected_revision` and `reason`. 409 when `expected_revision` is not the stored revision; 422 for out-of-range values or `max_range` below `effective_range`. A save that changes nothing keeps the revision. |
| DELETE | `/api/v1/admin/weapons/{code}?reason=` | `weapons.manage` | 204; 404 when there is no such weapon. |

This table (`weapon_balances`) is the tuning layer only; it does not replace `weapon_definitions`. Create, update and delete are audited (`weapon.create`, `weapon.update` with the changed fields, `weapon.delete`). Nothing reads these values at match time yet: the game runtime does not consume them.

### Asset library

Display images the admin console (and any client) can show, looked up by `kind` (`rank`, `prop`, `item`, `character`, `currency`, `badge`, `other`) and `key` (1–64 letters, digits, `.`, `-`, `_`; a prop id, item definition id, rank tier, `char_type` or currency code).

| Method | Path | Auth | Result |
| --- | --- | --- | --- |
| GET | `/api/v1/assets/{kind}/{key}` | none | The file bytes (an image, or `model/gltf-binary` for the `model` kind), `Cache-Control: public, max-age=86400`, `ETag`, `nosniff` and a sandbox CSP. 404 when there is none. |
| GET | `/api/v1/admin/assets?kind=&q=&limit=&offset=` | operator | Page of `id`, `kind`, `key`, `name`, `content_type`, `size_bytes`, `sha256`, `source`, `url` (`/api/v1/assets/{kind}/{key}?v=<hash>`), `created_at`, `updated_at`. |
| GET | `/api/v1/admin/assets/models/status` | operator | Which items, weapons, skins, original battle props and original lobby items have a 3D model. `items` has one row per target: `key` (`item-<id>`, `weapon-<code>`, `skin-<code>`, `prop-<prop id>` or `lobby-<lobby item id>`; lobby items only for the firearms, clothes, character, vehicles and companions categories), `type`, `code`, `label`, `detail`, `status` (`ready`, `missing`, or `unlinked` for a model nothing uses), `size_bytes`, `updated_at`, `url`. `summary` has `targets`, `ready`, `missing`, `unlinked`, `bytes` and `by_type` counts. |
| POST | `/api/v1/admin/assets` (multipart: `kind`, `key`, `name`, `source`, `upload`) | `assets.manage` | 201 and the row. The same kind and key replaces the file. |
| DELETE | `/api/v1/admin/assets/{id}` | `assets.manage` | 204. |

Only PNG, JPEG, GIF and WebP are accepted, checked from the file's own bytes; SVG is refused (415). Images are limited to 2 MB (413). The `model` kind takes binary glTF 2.0 (`.glb`) only, up to 25 MB, with textures packed inside; a `.glb` in any other kind, or an image in `model`, is 415, and a `.glb` whose header length does not match the file is 422. The admin panel shows `model/item-<id>` on that catalog item and `model/skin-<code>` on that store offer, falling back to the image card when there is none. Draco and KTX2 compression are not decoded. Files are stored by SHA-256 under `GAME_ASSET_DIR` (default `storage/game_assets/icons`, git-ignored) and removed when no row uses them. `source` records where each file came from; every upload, replace and delete is audited. `scripts/upload_assets.py <folder> --source "..."` uploads a `<kind>/<key>.<ext>` folder in one run (`--dry-run` lists it first).

### Operator sessions

`POST /api/v1/admin/auth/login` returns `access_token`, `expires_in` (seconds, `JWT_EXPIRE_MINUTES`) and `session_expires_at`: when this sign-in ends however often it is refreshed (`OPERATOR_SESSION_MAX_HOURS`, default 12, counted from the password sign-in).

`POST /api/v1/admin/auth/refresh` with a valid operator bearer token returns a new token of the same shape and the same `session_expires_at`. The old token keeps working for 30 seconds so requests already sent finish, then it is refused. A token's lifetime never runs past `session_expires_at`; once that time is reached, refresh answers 401 and the operator signs in again. Player tokens, revoked tokens and expired tokens get 401. `POST /api/v1/admin/auth/logout` revokes the token at once.

Operator management (all audited): `GET /api/v1/admin/operators` (`operators.read`) lists `id`, `username`, `status`, `roles`, `permissions` (effective codes), `last_login_at`, `created_at` and `active_sessions`. `PATCH /api/v1/admin/operators/{id}` with `status` `active` or `suspended` needs `operators.manage`; suspending ends every session, and an operator cannot suspend themselves or the last support operator. `POST /api/v1/admin/operators/{id}/password` with `password` (12+ characters) and `reason` sets a new password for another operator and ends their sessions. `POST /api/v1/admin/operators/{id}/sign-out` with an optional `reason` ends every session of that operator. Both answer `sessions_ended` and need `operators.manage`.

Roles (all audited): `GET /api/v1/admin/roles` (`roles.read`) lists `id`, `code`, `name`, `description`, `is_system`, `permissions`, `operator_count` and `created_at`. `POST /api/v1/admin/roles` (`roles.create`) returns `id`, `code`, `name`. `PATCH /api/v1/admin/roles/{id}` with `name` and/or `description` and `DELETE /api/v1/admin/roles/{id}` need `roles.create`; the system role cannot be renamed or deleted, and a role still held by an operator is not deleted (409). `PUT /api/v1/admin/roles/{id}/permissions` (`roles.assign`) grants only permissions the acting operator holds.

The admin panel refreshes in the background before expiry (a fifth of the lifetime early, 30 s to 5 min), shares the newest token across browser tabs through its session cookie, and warns five minutes before `session_expires_at`.

### Server log search

`GET /api/v1/admin/logs/search` (needs `logs.read`) reads `logs/server.log` from the newest line back and returns matching entries oldest first. Query: `start` and `end` (server local time, inclusive), repeated `level` (`ERROR`, `WARNING`, `INFO`, `DEBUG`), `q` (case-insensitive text), `kind` (`request` for `ros.function` request records, `app` for the rest) and `limit` (1–2000, default 500; the newest matches are kept). Each entry has `at` (`yyyy-MM-dd HH:mm:ss.SSS`), `level`, `logger`, `message`, `extra` (continuation lines such as tracebacks, up to 40) and `request` (`function_id`, `function_name`, `feature`, `status`, `duration_ms`, `error_code`, `error_message`, `request_id`, `player_id`, `match_id`) for request records. The response also has `counts` per level before the level filter, `truncated`, `oldest` and `newest`. Reading stops at `start`, so a recent range reads little of a large file. `GET /api/v1/admin/logs` still returns the raw tail.

### Operator live feed

`WS /api/v1/admin/ws` is for operators, not players. The first message must arrive within 5 seconds: `{"type": "auth", "payload": {"token": "<operator access token>"}}`. The token must hold `dashboard.read` or `players.read`; otherwise the server sends `error` and closes with 4003. Every server message is `{"version": 1, "type": ..., "payload": {...}}`:

| Type | Permission | Payload |
| --- | --- | --- |
| `auth.ok` | either | `operator`, `permissions` (the feed permissions held), `online_players`, `online_account_ids` (empty without `players.read`, 1000 at most) |
| `dashboard.snapshot` | `dashboard.read` | The `GET /api/v1/admin/dashboard` body plus `online_players`. Checked every 5 seconds and sent only when it changed. |
| `player.presence` | `players.read` | `account_id`, `online`, `online_players`, `source` (`socket` or `gateway`) when a player comes online or goes offline |
| `player.changed` | `players.read` | `account_id`, `change` (`profile`, `currency`, `item`, `prop`, `status`, or an account action), `operator` after an operator edit |
| `pong` | either | `online_players`, in reply to `{"type": "ping"}` |
| `error` | either | `detail` |

Live map: an operator holding `matches.read` sends `{"type": "watch", "payload": {"match_id": "<id>"}}` (or `null` for every running match) and then receives `match.frame` five times a second until `{"type": "unwatch"}`. A frame has `watching`, `tick`, `found` (false when the match is not in memory), `events` (engine events since the previous frame: `elimination`, `hit`, `pickup`, `heal`, `crate`, `phase`, `zone`, each with `tick` and `match_id`; at most 200) and `matches`, each with `match_id`, `phase`, `clock`, `map_size`, `alive`, `total`, `winner_id`, `zone` (`x`, `y`, `radius`, `next_x`, `next_y`, `next_radius`, `index`, `dps`), `players` (every combatant's `player_id`, `nickname`, `x`, `y`, `aim_x`, `aim_y`, `health`, `status`, `kills`, `weapon`, `vehicle`, `on_plane`, `bot`, `connected`), `vehicles`, `loot` (`[x, y]` pairs) and, on the first frame of a watch only, `blockers`. Frames are skipped, not queued, while the browser is behind. The engine keeps the last 2,000 events for this.

The token is checked again before each snapshot, so a revoked or expired token closes the socket with 4003. A socket idle for 60 seconds closes with 4004. An operator whose queue fills (256 messages) is dropped and closed with 1013. A player is online while they hold this server's game socket or while the gateway's presence lease is current. The gateway (`bigworld_gateway/server/account_link.py`) renews the lease every 20 seconds while the client sends packets and ends it after 45 seconds of silence; a lease that is not renewed expires after 75 seconds. Presence is held in memory, so a server restart starts everyone offline until the next report.

## Not implemented

Confirmed fact. These were requested by the game-services plan and are not routes:

- No leader role and no leader-transfer route.
- No durable equipment slots. `equip` is an in-memory match action.
- No HTTP matchmaking queue separate from the WebSocket. No Redis queue.
- No experience, currency, or inventory payout from match completion.
- No original client packet format.

Unknown. Original Rules of Survival authentication, lobby, matchmaking, and reward behavior.

## Original client item catalog (admin)

Read-only list of the original client's battle items, from `data/reference/original_battle_props.json` (text read from the client's prop table; no images). Needs an operator with `store.read`.

- `GET /api/v1/admin/original/props?type=<Gun|Bullet|...>&q=<name or id>` -> `{"items": [prop], "total": int, "types": {type: count}}`
- `GET /api/v1/admin/original/props/{id}` -> `prop`, 404 for an unknown id

`prop` = `{"id", "type", "name", "description", "icon_path", "pickup_icon_path", "weight", "capacity", "ros2"}`. Icons are uploaded by operators to the asset library as kind `prop`, key = the item id.

### Original client lobby content (admin)

From `data/reference/original_lobby.json` (text read from the client: `getDtsHallPropData`, Store goods, supply boxes, sets). Needs `store.read`. Icons: asset library kind `item`, key = lobby item id.

- `GET /api/v1/admin/original/lobby?category=<firearms|clothes|character|vehicles|items|companions|lobby_theme|actions|profile>&q=&offset=&limit=` -> `{"items": [item], "total", "offset", "limit", "categories": {category: count}}`; `item` = `{"id", "category", "type", "name", "description", "icon_path", "quality", "price": {"currency", "amount"} | null}`
- `GET /api/v1/admin/original/sets` -> `[{"id", "name", "gender", "items": [id], "item_names": [str]}]`
- `GET /api/v1/admin/original/store?q=&offset=&limit=` -> page of `{"id", "name", "currency", "price", "discount", "item_id", "locations"}`
- `GET /api/v1/admin/original/supply?kind=&on_sale=` -> `[{"id", "kind", "on_sale", "currencies", "price_once", "price_ten", "items", "item_count", "preview": [{"id", "name"}]}]`

### Lobby theme store listings (admin)

Operators set the price and on-sale state of the 21 lobby themes (`lobby_theme` items, prop ids 270000+) in the original client's in-game store. The game default for a theme is its client mall good: the `store` row of `original_lobby.json` whose `item_id` is the theme (from `bigworld_gateway/server/extract/mall_goods.json`). The price is that good's `price` after its `discount` %. 18 of the 21 themes have a mall good: 270000 Fearless Fiord (0 coins), 270002 Schoolgirl and 270004 Romantic Wedding (280 diamonds), 270003 Water Paradise (1280 diamonds), and 279001–279015 except 279004 (88888 diamonds each in the client table). 270001, 279004 and 279016 have none. A theme without one cannot be shown in the client store, so it cannot be put on sale. An override is one row in `store_listing_overrides`. Without a row the game default applies.

`LobbyThemeListing` = `{"id": int, "name": str, "description": str, "quality": int, "icon_path": str, "goods_id": int | null, "on_sale": bool, "currency": "diamond" | "coin", "price": int, "default_on_sale": bool, "default_currency": "diamond" | "coin" | null, "default_price": int | null, "overridden": bool, "background_url": str, "updated_at": str | null, "updated_by": str | null}`. `on_sale`, `currency` and `price` are the effective values: the override when there is one, else the game default. A theme with no game good and no override is `on_sale: false, currency: "diamond", price: 0`. `background_url` is the asset library `background` image for the theme id (`""` when none was uploaded). `updated_at` / `updated_by` (operator username) describe the override and are `null` without one.

| Method | Path | Permission | Body / query | Result |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/admin/original/lobby-themes` | `store.read` | optional filters, each matching one column: `q` (name or description substring, or exact theme id or goods id), `on_sale`, `currency` (`diamond`\|`coin`), `overridden`, `in_store` (true = `goods_id` set), `has_background`, `quality` (0..10). Booleans are `true`/`false`. Filters combine with AND, and `on_sale`/`currency` match the effective values. | `{"items": [LobbyThemeListing], "total": int}`: the matching themes (all 21 without filters) in catalog order. |
| PUT | `/api/v1/admin/original/lobby-themes/{theme_id}/listing` | `store.manage` | `{"on_sale": bool, "currency": "diamond" \| "coin", "price": 0..1000000, "reason": 1..200 chars}` | Saves the override and returns the `LobbyThemeListing`. 404 for an id that is not a lobby theme. 422 when `on_sale` is true for a theme with no `goods_id`, or for a bad body. |
| DELETE | `/api/v1/admin/original/lobby-themes/{theme_id}/listing?reason=` | `store.manage` | `reason` 1..200 chars (required) | Removes the override (back to the game default) and returns the `LobbyThemeListing`. 404 for an unknown id. |

PUT and DELETE write an operator audit entry with action `store.listing`, target type `lobby_theme`, target id = theme id, and the reason. `store.manage` is in the permission catalog. The built-in `support` role gets it, as it gets every catalog code. No role template holds `players.economy`, so no template was changed.

The gateway reads the overrides from `GET /api/v1/gateway/store/listings` (`X-Gateway-Key`, see the gateway section) -> `{"listings": [{"item_id", "goods_id", "on_sale", "currency", "price"}]}`. Only overridden items are listed. `bigworld_gateway/server/account_link.store_listings` caches the answer for 15 seconds, so a change reaches the store without a gateway restart. When RoS_Server is down or the link is off, the gateway uses the client's own prices. In the gateway, `diamond` is `const.MallCurrencyType.YUANBAO` (2) and `coin` is `GP` (1). An off-sale theme is left out of `onQueryAvailableMallGoods*`, and `buyMallGood`, `buyMultipleMallGood` and `buyDtsHallProp` refuse it with `onBuyMallGoodFailed`. An overridden price is listed with `DISCOUNT` 100 and charged as listed. The gateway keeps no coin balance, so coin goods are granted without a charge, as before.

# RoS Server

Local match server: accounts, a lobby, and a top-down match with bots, weapons, loot, and a shrinking zone.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`
- Play in a browser: `http://127.0.0.1:8000/play`
- Phone, same network: `http://<PC-LAN-IP>:8000/play`

Allow TCP port 8000 through Windows Firewall for private networks if the phone cannot connect.

## Match

Register, log in, then connect to `ws://<host>:8000/api/v1/ws`. The first message carries the token. Do not put the token in the URL.

```json
{"version":1,"type":"auth","sequence":1,"payload":{"token":"<access_token>"}}
```

Send `lobby.join` to enter the queue. A match starts about two seconds later. Bots fill empty slots, so one player can play. The drop phase follows a short countdown: send `player.action` with `{"action":"jump"}` to leave the plane.

Movement and aim share `player.input` (`move_x`, `move_y`, `aim_x`, `aim_y`, each from -1 to 1). Actions are `shoot`, `reload`, `pickup`, `use`, `equip`, `jump`, and `discard`. The server applies them. The 20 Hz tick sends a `state` message with your position, the zone, other players, and loot.

`GET /api/v1/players/me` includes kills, wins, and matches played. Those totals are written when a match ends.

## Engineering team

Task state lives in `.cursor/management/tasks.json`. Roles, assignment, and the CTO commands are documented in `docs/engineering/TEAM_STRUCTURE.md` and `docs/engineering/AGENT_ASSIGNMENT_GUIDE.md`.

```powershell
python scripts/validate_agent_registry.py
```

## Database

Development startup applies `alembic upgrade head` to the SQLite file in `DATABASE_URL`. Production should run that command before start and does not call `create_all`.

```powershell
alembic upgrade head
alembic current
python -m app.database.seeds.seed_all
python -m app.database.importers.import_data --source .\data\migration --dry-run
```

`alembic downgrade -1` is for a disposable database. It drops the new tables. Do not run it against a database you need to keep. See `docs/DATABASE_OPERATIONS.md`.

Copy `.env.example` when setting up another machine and replace `JWT_SECRET`.

Development uses SQLite. `docker-compose.yml` is the later PostgreSQL and Redis layout. Replace its example passwords before using it, and do not publish the database ports.

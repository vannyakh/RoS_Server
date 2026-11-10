# Environment audit

Audit date: 2026-11-10. Agent: devops-engineer. Registry tasks were not edited.

This note separates configuration that was read from commands that were executed. Labels are **Confirmed fact** or **Unknown**.

## What was executed

| Action | Result | Label |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe --version` in `C:\Users\LUFY\Desktop\RoS_Server` | Exit code 0. Output: `Python 3.12.10` | Confirmed fact |
| Read `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `pytest.ini`, `README.md`, `.gitignore`, and `docs/DATABASE_OPERATIONS.md` | All seven files were readable | Confirmed fact |
| Docker Compose, image build, container start, `docker` CLI | Not run | Confirmed fact |
| `pip`, `pytest`, `alembic`, `uvicorn`, PostgreSQL, and Redis | Not run | Confirmed fact |
| `.env` | Not opened. No secret values were printed | Confirmed fact |

The local interpreter to check is `.venv\Scripts\python.exe`. That path is the one that printed `Python 3.12.10`.

## Configured versus executed

### Python

| Item | Configured | Executed | Label |
| --- | --- | --- | --- |
| Local interpreter | `README.md` and `docs/DATABASE_OPERATIONS.md` tell Windows development to use `.\.venv\Scripts\Activate.ps1` and `.\.venv\Scripts\python.exe` | `.\.venv\Scripts\python.exe --version` printed `Python 3.12.10` | Confirmed fact |
| Image interpreter | `Dockerfile` starts from `python:3.12-slim` | Image was not pulled or started. The patch inside the image is not known | Image tag: Confirmed fact. Image contents: Unknown |
| PATH `python` | Not specified as the interpreter to check | Not run | Unknown |

### Application image

`Dockerfile` is configuration only. It was not built.

Confirmed fact from the file:

- `WORKDIR /app`
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`
- `pip install --no-cache-dir -r requirements.txt`
- Copies `app`, `migrations`, and `assets`
- `EXPOSE 8000`
- Process: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (no `--reload`)

Unknown: whether an image named from this Dockerfile exists on the machine, and whether that process has ever been started here.

### Compose

`docker-compose.yml` is configuration only. Compose was not started.

Confirmed fact from the file:

- `game-server` builds `.`, container name `ros-server`, `restart: unless-stopped`, publishes `8000:8000`
- `game-server` loads `env_file: .env`, then sets `DATABASE_URL` to `postgresql+asyncpg://ros:CHANGE_ME@postgres:5432/ros` and `REDIS_URL` to `redis://redis:6379/0`
- `game-server` waits for `postgres` healthy and `redis` started
- `postgres` uses image `postgres:17`, container `ros-postgres`, user `ros`, database `ros`, password placeholder `CHANGE_ME`, volume `postgres_data`, and `pg_isready -U ros -d ros`
- `redis` uses image `redis:7-alpine`, container `ros-redis`, `redis-server --appendonly yes`, volume `redis_data`
- PostgreSQL and Redis have no `ports:` entries, so the file does not publish database ports
- Named volumes: `postgres_data`, `redis_data`

`CHANGE_ME` is the placeholder stored in the Compose file. It is not a supplied secret.

Unknown: whether Docker is installed, whether the engine is running, whether `ros-server`, `ros-postgres`, or `ros-redis` exist, and whether the named volumes contain data. No live infrastructure test was performed.

### Python packages and tests

`requirements.txt` pins ranges, not a lockfile. Confirmed packages in that file:

- `fastapi>=0.115,<1.0`
- `uvicorn[standard]>=0.34`
- `pydantic-settings>=2.7`
- `sqlalchemy[asyncio]>=2.0`
- `aiosqlite>=0.20`
- `asyncpg>=0.30`
- `pwdlib[argon2]>=0.2`
- `PyJWT>=2.10`
- `python-multipart>=0.0.20`
- `redis>=5.2`
- `alembic>=1.14`
- `pytest>=8.3`
- `pytest-asyncio>=0.25`
- `httpx>=0.28`
- `prometheus-client>=0.26`
- `opentelemetry-api>=1.27`
- `opentelemetry-sdk>=1.27`
- `sentry-sdk>=2.19`
- `locust>=2.32`
- `websocket-client>=1.8`

The same file is what the image installs, so a built image would include pytest, Locust, and the observability libraries. Whether those distributions are installed in `.venv` was not checked.

`pytest.ini` sets `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`, and `pythonpath = .`. Pytest was not run, so the suite result is Unknown.

`docs/DATABASE_OPERATIONS.md` documents `.\.venv\Scripts\python.exe -m pytest tests -q` and says a PostgreSQL test runs only when `POSTGRES_TEST_URL` is set. That variable was not set or read in this audit. Whether the suite would skip PostgreSQL is Unknown for this run.

### Documented local run

`README.md` configures a host process, not Compose, for local play:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Documented URLs are `http://127.0.0.1:8000/health`, `/docs`, and `/play`. That server was not started. Whether anything is listening on port 8000 is Unknown.

`README.md` states development uses SQLite, startup applies `alembic upgrade head`, and production should migrate before start. `docs/DATABASE_OPERATIONS.md` states `alembic history` shows revision `93510e8bf194`, SQLite uses a null pool, and PostgreSQL uses `pool_pre_ping` with pool size 10 and max overflow 20. Alembic was not run, and no database file was opened, so the live revision and the live `DATABASE_URL` are Unknown.

Disposable downgrade is documented as `alembic downgrade -1` on a copy or temporary file. It was not run. `ros_server.db` was not opened or modified.

### Ignore rules

`.gitignore` ignores `.venv/`, `__pycache__/`, `*.pyc`, `.env`, `*.db`, `*.bak`, `.pytest_cache/`, `reports/player/`, and `logs/*.log`. It does not list `reports/project-audit/`. Whether this audit file is tracked is Unknown because git status was not run.

## Unknown, left unknown on purpose

- Docker engine, images, containers, and volumes
- Installed package set inside `.venv`
- Pytest result
- Current Alembic revision and database file contents
- Contents of `.env`, including `JWT_SECRET`
- Whether PostgreSQL or Redis is reachable
- Whether the host process on port 8000 is running

## Task report

```text
TASK ID:
Not a registry task. RO-010 and RO-026 are already completed. RO-034 is backlog and was not started. tasks.json was not modified.

AGENT:
devops-engineer

PHASE:
Environment audit only.

STATUS:
Report written. No registry status change.

IMPLEMENTATION:
Read-only inspection of the runtime configuration. One audit file written.

FILES CREATED:
reports/project-audit/environment.md

FILES MODIFIED:
None.

DISCOVERIES:
.venv\Scripts\python.exe is Python 3.12.10. Compose defines PostgreSQL 17 and Redis 7 with placeholder password CHANGE_ME and no published database ports. The image base is python:3.12-slim and was not built. Docker was not started.

DATABASE CHANGES:
None.

API CHANGES:
None.

GAME FUNCTION CHANGES:
None.

TESTS EXECUTED:
.\.venv\Scripts\python.exe --version

TEST RESULTS:
Exit code 0. Output: Python 3.12.10. Pytest was not run.

COMPATIBILITY EVIDENCE:
None. This audit does not classify game compatibility.

KNOWN ISSUES:
Container runtime state, installed dependencies, the live database revision, and .env were not verified.

RECOMMENDATION:
Keep Compose stopped until the user asks for a live infrastructure test and replaces CHANGE_ME. Do not publish database ports. Do not run alembic downgrade against ros_server.db.

OBJECTIVE:
Record configured environment versus commands actually executed.

IMPLEMENTATION SUMMARY:
One report file. Interpreter version confirmed. Docker, pytest, Alembic, and secret files were not executed or opened.

SECURITY CONSIDERATIONS:
.env was not read. JWT_SECRET was not printed. The only password string recorded is the Compose placeholder CHANGE_ME.

DEPENDENCIES:
None executed. Compose file declares postgres healthy and redis started before game-server. That graph was not started.
```

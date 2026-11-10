# Architecture decisions

## Server shape

The server is a Python 3.12 FastAPI modular monolith. HTTP and WebSocket code call services. Services call repositories. Repositories use async SQLAlchemy 2. The 20 Hz match loop keeps positions in memory and writes totals only after a result exists.

The wire protocol is this project's JSON protocol. It is not an official Rules of Survival client protocol.

## Identity

`accounts` is the login row and the JWT subject. `players` is one profile per account, with a unique nickname. Statistics live on `player_statistics`. Passwords are Argon2 hashes. Session tokens are stored as SHA-256 hashes and are omitted from response schemas.

## Schema portability

Primary keys are UUID strings so one Alembic revision serves SQLite and PostgreSQL. JSON columns use `PortableJSON` (JSON on SQLite, JSONB on PostgreSQL). The Python attribute is `details` because `metadata` is reserved by SQLAlchemy. Relationships use `lazy="raise"`.

## Legacy data

Revision `93510e8bf194` renames the original `players` table to `legacy_players`, creates the new tables, and copies rows. Upgrade does not drop the legacy table. Downgrade is for a disposable database.

## Management

Task state lives in `.cursor/management/tasks.json`. The CTO is the only role that assigns tasks. Specialists do not edit the registry and do not approve their own work. Two active tasks cannot list overlapping write paths.

RO-009, the independent security review, is still open. RO-011 stays blocked until that review is recorded.

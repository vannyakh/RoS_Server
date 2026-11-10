"""Create one active account from the command line."""

import asyncio
import sys

from sqlalchemy import select

from app.infrastructure.database import SessionLocal, close_db, init_db
from app.models.account import Account
from app.services.auth_service import normalize_username, register_player


async def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python scripts/create_admin.py <username> <password>")
    username, password = sys.argv[1], sys.argv[2]
    await init_db()
    async with SessionLocal() as session:
        existing = await session.scalar(select(Account).where(Account.username == normalize_username(username)))
        if existing is None:
            account = await register_player(session, username, password)
            print(f"Created {account.username} ({account.id})")
        else:
            print(f"Account already exists: {existing.username}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())

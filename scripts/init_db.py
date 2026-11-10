"""Create the development database tables."""

import asyncio

from app.infrastructure.database import close_db, init_db


async def main() -> None:
    await init_db()
    await close_db()
    print("Database schema is ready.")


if __name__ == "__main__":
    asyncio.run(main())

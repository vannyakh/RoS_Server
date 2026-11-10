"""Account queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, LoginHistory


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_id(self, account_id: str) -> Account | None:
        return await self.session.get(Account, account_id)

    async def by_username(self, username: str) -> Account | None:
        return await self.session.scalar(select(Account).where(Account.username == username))

    async def add(self, account: Account) -> Account:
        self.session.add(account)
        await self.session.flush()
        return account

    async def add_login(self, entry: LoginHistory) -> None:
        self.session.add(entry)
        await self.session.flush()

    async def page(self, limit: int, offset: int) -> tuple[list[Account], int]:
        rows = (
            await self.session.scalars(select(Account).order_by(Account.created_at).limit(limit).offset(offset))
        ).all()
        total = int(await self.session.scalar(select(func.count()).select_from(Account)) or 0)
        return list(rows), total

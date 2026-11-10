"""Idempotent reference-data upserts. Repeated runs update the fixture and do not touch player rows."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_code(session: AsyncSession, model, code: str, **values):
    row = await session.scalar(select(model).where(model.code == code))
    if row is None:
        row = model(code=code, **values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    await session.flush()
    return row

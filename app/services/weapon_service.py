"""Weapon balance: operators read and tune each weapon's combat numbers. Every change is audited."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.weapon_balance import WEAPON_CLASSES, WeaponBalance
from app.services.operator_service import OperatorActor, OperatorService

CODE = re.compile(r"[a-z0-9_]{1,32}")
FIELDS = (
    "name", "weapon_class", "damage", "fire_rate", "magazine", "reload_seconds", "effective_range", "max_range",
    "falloff_percent", "spread", "recoil", "head_multiplier", "torso_multiplier", "limb_multiplier", "vehicle_damage",
)


def view(row: WeaponBalance) -> dict:
    return {"code": row.code, **{field: getattr(row, field) for field in FIELDS}, "revision": row.revision, "updated_at": row.updated_at}


class WeaponService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operators = OperatorService(session)

    async def listing(self, actor: OperatorActor) -> list[dict]:
        self.operators._need(actor, "weapons.read")
        rows = await self.session.scalars(select(WeaponBalance).order_by(WeaponBalance.weapon_class, WeaponBalance.code))
        return [view(row) for row in rows]

    async def save(self, actor: OperatorActor, code: str, values: dict, expected_revision: int | None, reason: str) -> dict:
        self.operators._need(actor, "weapons.manage")
        if not CODE.fullmatch(code):
            raise AppError(422, "Code must be 1-32 lowercase letters, digits or underscores")
        if values["weapon_class"] not in WEAPON_CLASSES:
            raise AppError(422, "Unknown weapon class")
        if values["max_range"] < values["effective_range"]:
            raise AppError(422, "Max range cannot be below the effective range")
        row = await self.session.scalar(select(WeaponBalance).where(WeaponBalance.code == code))
        if row is None:
            if expected_revision not in (None, 0):
                raise AppError(409, "This weapon no longer exists")
            row = WeaponBalance(code=code, revision=0, **{field: values[field] for field in FIELDS})
            self.session.add(row)
            changed = list(FIELDS)
            action = "weapon.create"
        else:
            if expected_revision is not None and expected_revision != row.revision:
                raise AppError(409, "This weapon was changed by someone else. Reload it and apply the edit again")
            changed = [field for field in FIELDS if getattr(row, field) != values[field]]
            for field in changed:
                setattr(row, field, values[field])
            action = "weapon.update"
        if not changed:
            return view(row)
        row.revision += 1
        row.updated_by = actor.operator.id
        await self.session.flush()
        detail = ", ".join(f"{field}={values[field]}" for field in changed) if action == "weapon.update" else row.name
        await self.operators._audit(actor, action, "weapon_balance", row.id, f"{code}: {detail}"[:240], reason)
        await self.session.commit()
        return view(row)

    async def delete(self, actor: OperatorActor, code: str, reason: str) -> None:
        self.operators._need(actor, "weapons.manage")
        row = await self.session.scalar(select(WeaponBalance).where(WeaponBalance.code == code))
        if row is None:
            raise AppError(404, "Weapon was not found")
        await self.operators._audit(actor, "weapon.delete", "weapon_balance", row.id, code, reason)
        await self.session.delete(row)
        await self.session.commit()

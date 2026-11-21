"""Weapon balance routes for the admin console."""

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import current_operator
from app.infrastructure.database import get_db
from app.models.weapon_balance import WEAPON_CLASSES
from app.services.operator_service import OperatorActor
from app.services.weapon_service import WeaponService

router = APIRouter(prefix="/admin/weapons", tags=["Weapons"])

CODE = "^[a-z0-9_]{1,32}$"


class WeaponBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weapon_class: str = Field(pattern="^(" + "|".join(WEAPON_CLASSES) + ")$")
    damage: float = Field(gt=0, le=1000)
    fire_rate: float = Field(ge=1, le=3000)
    magazine: int = Field(ge=0, le=500)
    reload_seconds: float = Field(ge=0, le=30)
    effective_range: float = Field(ge=0, le=3000)
    max_range: float = Field(ge=0, le=3000)
    falloff_percent: float = Field(ge=0, le=100)
    spread: float = Field(ge=0, le=45)
    recoil: float = Field(ge=0, le=100)
    head_multiplier: float = Field(ge=0, le=10)
    torso_multiplier: float = Field(ge=0, le=10)
    limb_multiplier: float = Field(ge=0, le=10)
    vehicle_damage: float = Field(ge=0, le=1000)
    # The revision the editor loaded. A mismatch means someone else saved first (409).
    expected_revision: int | None = Field(default=None, ge=0)
    reason: str = Field(default="", max_length=240)

    @model_validator(mode="after")
    def ranges_in_order(self) -> "WeaponBody":
        if self.max_range < self.effective_range:
            raise ValueError("max_range cannot be below effective_range")
        return self


@router.get("")
async def list_weapons(actor: OperatorActor = Depends(current_operator), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await WeaponService(db).listing(actor)


@router.put("/{code}")
async def save_weapon(
    body: WeaponBody,
    code: str = Path(pattern=CODE),
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> dict:
    values = body.model_dump(exclude={"expected_revision", "reason"})
    return await WeaponService(db).save(actor, code, values, body.expected_revision, body.reason)


@router.delete("/{code}", status_code=204)
async def delete_weapon(
    code: str = Path(pattern=CODE),
    reason: str = Query(default="", max_length=240),
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> None:
    await WeaponService(db).delete(actor, code, reason)

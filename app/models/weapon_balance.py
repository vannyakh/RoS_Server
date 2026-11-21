"""Per-weapon combat tuning edited from the admin console, keyed by a stable weapon code.

This is the balance layer only: names and numbers an operator can change without a deploy.
It does not replace `weapon_definitions`, which holds the imported catalog.
"""

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, UpdatedAtMixin

WEAPON_CLASSES = ("assault", "smg", "sniper", "shotgun", "pistol", "melee")


class WeaponBalance(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "weapon_balances"
    __table_args__ = (
        CheckConstraint("weapon_class IN ('assault', 'smg', 'sniper', 'shotgun', 'pistol', 'melee')", name="weapon_class"),
        CheckConstraint("damage > 0", name="damage"),
        CheckConstraint("max_range >= effective_range", name="range_order"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    weapon_class: Mapped[str] = mapped_column(String(16), nullable=False)
    damage: Mapped[float] = mapped_column(Float, nullable=False)
    fire_rate: Mapped[float] = mapped_column(Float, nullable=False)  # rounds per minute
    magazine: Mapped[int] = mapped_column(Integer, nullable=False)
    reload_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    effective_range: Mapped[float] = mapped_column(Float, nullable=False)  # metres at full damage
    max_range: Mapped[float] = mapped_column(Float, nullable=False)
    falloff_percent: Mapped[float] = mapped_column(Float, nullable=False)  # damage lost at max range
    spread: Mapped[float] = mapped_column(Float, nullable=False)  # degrees
    recoil: Mapped[float] = mapped_column(Float, nullable=False)  # 0..100
    head_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    torso_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    limb_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    vehicle_damage: Mapped[float] = mapped_column(Float, nullable=False)  # percent
    # Bumped on every change; a client can send it back to refuse overwriting a newer edit.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)

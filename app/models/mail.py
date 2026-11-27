"""Mail an operator sends to one player. The original client reads it through the gateway."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON


class PlayerMail(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "player_mails"
    __table_args__ = (UniqueConstraint("number", name="uq_player_mails_number"),)

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    # The client's mailID is an INT32. It starts high so it cannot collide with the gateway's lobby_mail.json ids.
    number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    sender: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # [[prop_id, count], ...]; granted once, by the claim route.
    props: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id", ondelete="SET NULL"), nullable=True)

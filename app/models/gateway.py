"""Original-client identities. One row links a BigWorld gateway login uid to one account."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.types import CreatedAtMixin, IdMixin, PortableJSON, UpdatedAtMixin


class GatewayIdentity(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "gateway_identities"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_gateway_identities_account_id"),
        UniqueConstraint("external_uid", name="uq_gateway_identities_external_uid"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    external_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    # Original-client career type chosen at character creation. Null until the character exists.
    char_type: Mapped[int | None] = mapped_column(nullable=True)
    # Uploaded avatar: FilePicker file id. Empty means the built-in image for char_type.
    portrait: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    # Worn original-client appearance ids: {"body": [...], "wear": [...]}. Null until first change.
    outfit: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    account: Mapped["Account"] = relationship(lazy="raise")


class GatewayItem(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """An original-client hall prop (appearance item) owned by a gateway player. prop_id is the
    client's own id; these items are separate from this server's item catalog."""

    __tablename__ = "gateway_items"
    __table_args__ = (
        CheckConstraint("number >= 0", name="number"),
        UniqueConstraint("identity_id", "prop_id", name="uq_gateway_items_identity_prop"),
    )

    identity_id: Mapped[str] = mapped_column(
        ForeignKey("gateway_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prop_id: Mapped[int] = mapped_column(nullable=False)
    number: Mapped[int] = mapped_column(default=1, nullable=False)

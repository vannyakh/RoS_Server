"""Original-client identities. One row links a BigWorld gateway login uid to one account."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
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
    # Worn avatar frame: an original-client HeadFrameAppearanceType prop id. 0 means no frame.
    head_frame: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    national_flag: Mapped[str] = mapped_column(String(8), nullable=False, default="", server_default="")
    # Worn original-client appearance ids: {"body": [...], "wear": [...]}. Null until first change.
    outfit: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Ranked score: the client turns it into the tier badge (Bronze .. King) and stars.
    rank_score: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    # Credit system (client credit_system_common): score starts at 100 and is capped at 160.
    credit_score: Mapped[int] = mapped_column(default=100, server_default="100", nullable=False)
    # Weekly credit authentication from last week: 0 none, 1 silver, 2 gold, 3 diamond.
    credit_status_last_week: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    # Consecutive weeks with an authentication ("Consecutive N Week(s)").
    credit_weeks: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    # Unclaimed weekly credit reward prop ids; emptied by the Claim button.
    credit_gifts: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)
    # Likes received on the player's personal space (My Page).
    space_likes: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    account: Mapped["Account"] = relationship(lazy="raise")


RECORD_QUEUES = ("total", "ranked", "matching")
RECORD_TEAM_MODES = ("overall", "solo", "dual", "quad", "five")


class GatewayBattleRecord(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """Battle record totals for one (season, queue, team mode), as the client Stats page shows them.

    season 0 holds all-time totals. queue is total / ranked / matching and team_mode is
    overall / solo / dual / quad / five, which together name the client's record types
    (const.RecordTypeToName). Distances are in decimetres, as the client sends and divides them.
    """

    __tablename__ = "gateway_battle_records"
    __table_args__ = (
        UniqueConstraint("identity_id", "season", "queue", "team_mode", name="uq_gateway_battle_records_key"),
        CheckConstraint("season >= 0", name="season"),
        CheckConstraint("queue IN ('total', 'ranked', 'matching')", name="queue"),
        CheckConstraint("team_mode IN ('overall', 'solo', 'dual', 'quad', 'five')", name="team_mode"),
        CheckConstraint(
            "fight_count >= 0 AND win_count >= 0 AND top5_count >= 0 AND kill_count >= 0 AND death_count >= 0",
            name="counts",
        ),
    )

    identity_id: Mapped[str] = mapped_column(
        ForeignKey("gateway_identities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[int] = mapped_column(nullable=False)
    queue: Mapped[str] = mapped_column(String(16), nullable=False)
    team_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    fight_count: Mapped[int] = mapped_column(default=0, nullable=False)
    win_count: Mapped[int] = mapped_column(default=0, nullable=False)
    top5_count: Mapped[int] = mapped_column(default=0, nullable=False)
    kill_count: Mapped[int] = mapped_column(default=0, nullable=False)
    death_count: Mapped[int] = mapped_column(default=0, nullable=False)
    assist_count: Mapped[int] = mapped_column(default=0, nullable=False)
    damage: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    head_shot_count: Mapped[int] = mapped_column(default=0, nullable=False)
    hit_count: Mapped[int] = mapped_column(default=0, nullable=False)
    fire_count: Mapped[int] = mapped_column(default=0, nullable=False)
    fight_time_seconds: Mapped[int] = mapped_column(default=0, nullable=False)
    collect_count: Mapped[int] = mapped_column(default=0, nullable=False)
    heal_count: Mapped[int] = mapped_column(default=0, nullable=False)

    max_round_kill: Mapped[int] = mapped_column(default=0, nullable=False)
    max_round_assist: Mapped[int] = mapped_column(default=0, nullable=False)
    max_round_heal: Mapped[int] = mapped_column(default=0, nullable=False)
    max_kill_distance_dm: Mapped[int] = mapped_column(default=0, nullable=False)
    max_move_distance_dm: Mapped[int] = mapped_column(default=0, nullable=False)
    max_fight_time_seconds: Mapped[int] = mapped_column(default=0, nullable=False)


class GatewayCreditRecord(IdMixin, CreatedAtMixin, Base):
    """One credit score change. reason is the client's CREDIT_CHANGE_REASON code (-1 = server/admin)."""

    __tablename__ = "gateway_credit_records"
    __table_args__ = (Index("ix_gateway_credit_records_identity_created", "identity_id", "created_at"),)

    identity_id: Mapped[str] = mapped_column(ForeignKey("gateway_identities.id", ondelete="CASCADE"), nullable=False)
    delta: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[int] = mapped_column(nullable=False)
    score_after: Mapped[int] = mapped_column(nullable=False)
    note: Mapped[str] = mapped_column(String(128), default="", server_default="", nullable=False)


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

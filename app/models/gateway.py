"""Original-client identities. One row links a BigWorld gateway login uid to one account."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, true
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


MAIL_TYPE_TXT = 0    # client SysMailTypeEnum.TXT: text only
MAIL_TYPE_PROPS = 1  # client SysMailTypeEnum.PROPS: has attachments or gold (gift icon)
MAIL_MAX_ATTACHMENTS = 6  # the client detail view shows prop_1 .. prop_6


class GatewayMail(IdMixin, CreatedAtMixin, Base):
    """System mail for one original-client player (client screen UISystemMail).

    mail_id is the client's INT32 mailID: a per-identity sequence starting at 1. attachments is
    [{"prop_id", "number"}] (at most 6). read_at / claimed_at / deleted_at are null until the
    player opens, claims or deletes the mail; a mail past its deadline is hidden and unclaimable.
    """

    __tablename__ = "gateway_mails"
    __table_args__ = (
        UniqueConstraint("identity_id", "mail_id", name="uq_gateway_mails_identity_mail"),
        CheckConstraint("mail_id >= 1", name="mail_id"),
        CheckConstraint("mail_type IN (0, 1)", name="mail_type"),
        CheckConstraint("gold >= 0", name="gold"),
        Index("ix_gateway_mails_identity_sent", "identity_id", "sent_at"),
    )

    identity_id: Mapped[str] = mapped_column(ForeignKey("gateway_identities.id", ondelete="CASCADE"), nullable=False)
    mail_id: Mapped[int] = mapped_column(nullable=False)
    mail_type: Mapped[int] = mapped_column(default=MAIL_TYPE_TXT, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    sender: Mapped[str] = mapped_column(String(32), nullable=False, default="System")
    attachments: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)
    gold: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Operator username that sent it; null for mail the server sent itself.
    sent_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


SERVER_STATUSES = ("auto", "smooth", "busy", "full", "maintenance")


class GatewayServer(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """One original-client gateway process, as listed on the game's server-select screen.

    The gateway reports itself (address, version, player counts) on every heartbeat; operators set
    the display name, status and whether it is listed. status "auto" derives smooth/busy/full from
    players_online / capacity. A server not heard from for HEARTBEAT_LIVE_SECONDS counts as down.
    """

    __tablename__ = "gateway_servers"
    __table_args__ = (
        UniqueConstraint("server_key", name="uq_gateway_servers_key"),
        CheckConstraint("status IN ('auto', 'smooth', 'busy', 'full', 'maintenance')", name="status"),
        CheckConstraint("capacity >= 1", name="capacity"),
        CheckConstraint("port >= 1 AND port <= 65535", name="port"),
        CheckConstraint("players_online >= 0 AND players_in_match >= 0", name="players"),
    )

    server_key: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    host: Mapped[str] = mapped_column(String(253), nullable=False)
    port: Mapped[int] = mapped_column(nullable=False)
    zone: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    group_id: Mapped[int] = mapped_column(default=10001, server_default="10001", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="auto", server_default="auto", nullable=False)
    capacity: Mapped[int] = mapped_column(default=100, server_default="100", nullable=False)
    listed: Mapped[bool] = mapped_column(default=True, server_default=true(), nullable=False)
    version: Mapped[str] = mapped_column(String(64), default="", server_default="", nullable=False)
    players_online: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    players_in_match: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

"""Messages between the original-client gateway and this server."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

EXTERNAL_UID_PATTERN = r"^[0-9A-Za-z_.\-]{1,64}$"


class GatewayPresence(BaseModel):
    """Original-client session report. online=true renews a 75-second lease; false ends it."""

    online: bool


class GatewayDevice(BaseModel):
    """What the client's SDK requests reported for this device (User-Agent and query string)."""

    model: str | None = Field(default=None, max_length=64)
    os_name: str | None = Field(default=None, max_length=32)
    client_version: str | None = Field(default=None, max_length=32)
    time_zone: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=16)


class GatewayResolveRequest(BaseModel):
    external_uid: str = Field(pattern=EXTERNAL_UID_PATTERN)
    ip_address: str | None = Field(default=None, max_length=64)
    device: GatewayDevice | None = None


class GatewayCharacterRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=32)
    char_type: int = Field(ge=0)


PORTRAIT_PATTERN = r"^[0-9A-Za-z_.\-]{0,128}$"


class GatewayPortraitRequest(BaseModel):
    portrait: str = Field(pattern=PORTRAIT_PATTERN)


NATIONAL_FLAG_PATTERN = r"^[A-Za-z]{0,8}$"


class GatewayHeadFrameRequest(BaseModel):
    head_frame: int = Field(ge=0, le=2_147_483_647)


class GatewayNationalFlagRequest(BaseModel):
    national_flag: str = Field(pattern=NATIONAL_FLAG_PATTERN)


class GatewayAccount(BaseModel):
    account_id: str
    username: str
    status: str
    can_play: bool
    is_new: bool
    nickname: str
    char_type: int | None
    portrait: str = ""
    national_flag: str = ""
    head_frame: int = 0


PROP_IDS = Field(default_factory=list, max_length=200)


class GatewayItemView(BaseModel):
    prop_id: int
    number: int


class GatewayOutfit(BaseModel):
    body: list[int] = Field(default_factory=list, max_length=64)
    wear: list[int] = Field(default_factory=list, max_length=64)
    weapon: list[int] = Field(default_factory=list, max_length=32)
    vehicle: list[int] = Field(default_factory=list, max_length=32)
    # Vehicle skins shown beside the player in the lobby (Depot > Vehicles > Display).
    hall_vehicle: list[int] = Field(default_factory=list, max_length=8)
    # When set, lobby display lists differ from the equipped lists (Depot preview / Display).
    show_weapon: list[int] = Field(default_factory=list, max_length=32)
    show_vehicle: list[int] = Field(default_factory=list, max_length=32)
    # Lobby theme (hall background) prop id; 0 keeps the client default.
    theme: int = Field(default=0, ge=0)
    # Depot > Recent tab (Athlete.recentGotPropIDList), newest first, capped at 20.
    recent_got: list[int] = Field(default_factory=list, max_length=20)


class GatewayState(BaseModel):
    """What the gateway needs at login: diamonds, owned appearance items, worn outfit."""

    yuanbao: int
    items: list[GatewayItemView]
    outfit: GatewayOutfit
    head_frame: int = 0
    # Depot > Recent tab (Athlete.recentGotPropIDList), newest first, capped at 20.
    recent_got: list[int] = Field(default_factory=list, max_length=20)
    # Original-client currency balances keyed by the client currency id as a string: {"1": gold}.
    currencies: dict[str, int] = Field(default_factory=dict)


class GatewayPurchaseRequest(BaseModel):
    """Pay `price` diamonds (0 for draws paid in other client currencies) and add `props`."""

    price: int = Field(ge=0, le=1_000_000)
    props: list[int] = PROP_IDS
    reason: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_.:-]+$")
    # Optional idempotency key. A repeated id for the same player replays the first result.
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")


class GatewayPurchaseResult(BaseModel):
    yuanbao: int
    added: list[int]
    recent_got: list[int] = Field(default_factory=list, max_length=20)
    replayed: bool = False


REQUEST_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
LEDGER_REASON_PATTERN = r"^[a-z0-9_.:-]+$"


class GatewayTopupRequest(BaseModel):
    """Credit diamonds without charging an in-game purchase price (private IAP / operator grant)."""

    amount: int = Field(ge=1, le=1_000_000)
    reference: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_.:-]+$")
    reason: str = Field(default="gateway:topup", min_length=1, max_length=64, pattern=LEDGER_REASON_PATTERN)


class GatewayTopupResult(BaseModel):
    yuanbao: int
    replayed: bool = False
PROP_ID = Field(ge=0, le=2_147_483_647)
PROP_LIST = Field(default_factory=list, max_length=50)


class GatewayPropCount(BaseModel):
    prop_id: int = PROP_ID
    number: int = Field(ge=1, le=1_000_000)


class GatewayCurrencyAmount(BaseModel):
    """Only client currency 1 (gold coins) is stored; any other id is answered 422."""

    currency_id: Literal[1]
    amount: int = Field(ge=0, le=1_000_000_000)


class GatewayCompoundRequest(BaseModel):
    """Workshop recipe the gateway validated: own `require`, spend `consume` and gold, gain `add`."""

    request_id: str = Field(pattern=REQUEST_ID_PATTERN)
    require: list[GatewayPropCount] = PROP_LIST
    consume: list[GatewayPropCount] = PROP_LIST
    consume_currency: list[GatewayCurrencyAmount] = Field(default_factory=list, max_length=4)
    add: list[GatewayPropCount] = PROP_LIST
    reason: str = Field(min_length=1, max_length=64, pattern=LEDGER_REASON_PATTERN)


class GatewayCompoundResult(BaseModel):
    items: list[GatewayItemView]
    currencies: dict[str, int]
    replayed: bool = False


class GatewayDevGrantRequest(BaseModel):
    props: list[GatewayPropCount] = PROP_LIST
    currencies: list[GatewayCurrencyAmount] = Field(default_factory=list, max_length=4)


QUEUE_PATTERN = r"^(total|ranked|matching)$"
TEAM_MODE_PATTERN = r"^(solo|dual|quad|five)$"


class GatewayBattleRecordView(BaseModel):
    """Totals for one season / queue / team mode. Distances are decimetres (client units)."""

    season: int
    queue: str
    team_mode: str
    fight_count: int = 0
    win_count: int = 0
    top5_count: int = 0
    kill_count: int = 0
    death_count: int = 0
    assist_count: int = 0
    damage: int = 0
    head_shot_count: int = 0
    hit_count: int = 0
    fire_count: int = 0
    fight_time_seconds: int = 0
    collect_count: int = 0
    heal_count: int = 0
    max_round_kill: int = 0
    max_round_assist: int = 0
    max_round_heal: int = 0
    max_kill_distance_dm: int = 0
    max_move_distance_dm: int = 0
    max_fight_time_seconds: int = 0


class GatewayCreditRecordView(BaseModel):
    delta: int
    reason: int
    score_after: int
    note: str
    created_at: datetime


class GatewayCredit(BaseModel):
    score: int
    status_last_week: int
    weeks: int
    gifts: list[int]
    records: list[GatewayCreditRecordView]


class GatewayProfile(BaseModel):
    """What the client's My Page, Stats and Credit screens show for one player."""

    nickname: str
    level: int
    char_type: int | None
    portrait: str
    national_flag: str = ""
    head_frame: int = 0
    # Store paths from the asset library; empty when no image was uploaded for them.
    rank_tier: str = ""
    rank_logo_url: str = ""
    lobby_theme: int = 0
    lobby_background_url: str = ""
    rank_score: int
    space_likes: int
    current_season: int
    credit: GatewayCredit
    records: list[GatewayBattleRecordView]


class GatewayMatchReport(BaseModel):
    """One finished match. Adds to the season and all-time rows for this mode and for 'overall'."""

    season: int | None = Field(default=None, ge=1, le=10_000)
    queue: str = Field(default="total", pattern=QUEUE_PATTERN)
    team_mode: str = Field(default="solo", pattern=TEAM_MODE_PATTERN)
    placement: int = Field(ge=1, le=200)
    kills: int = Field(default=0, ge=0, le=200)
    deaths: int = Field(default=0, ge=0, le=200)
    assists: int = Field(default=0, ge=0, le=200)
    damage: int = Field(default=0, ge=0, le=10_000_000)
    head_shots: int = Field(default=0, ge=0, le=100_000)
    hits: int = Field(default=0, ge=0, le=100_000)
    fires: int = Field(default=0, ge=0, le=1_000_000)
    fight_time_seconds: int = Field(default=0, ge=0, le=36_000)
    collect_count: int = Field(default=0, ge=0, le=10_000)
    heal_count: int = Field(default=0, ge=0, le=10_000)
    kill_distance_dm: int = Field(default=0, ge=0, le=100_000)
    move_distance_dm: int = Field(default=0, ge=0, le=10_000_000)
    rank_score_delta: int = Field(default=0, ge=-10_000, le=10_000)


class GatewayCreditClaim(BaseModel):
    """Props granted by the weekly credit reward (empty when nothing was waiting)."""

    awards: list[int]
    credit: GatewayCredit



# System mail (RO-117). Keys match what the client's UISystemMail reads; see
# bigworld_gateway/docs/MAIL_FINDINGS.md. Times are unix seconds; deadline 0 means none.
MAIL_ATTACHMENTS = 6


class GatewayMailAttachment(BaseModel):
    prop_id: int = PROP_ID
    number: int = Field(ge=1, le=999)


class GatewayMailView(BaseModel):
    mail_id: int
    type: int
    title: str
    sender: str
    abstract: str
    sent_at: int
    deadline: int
    unread: bool
    claimed: bool
    attachments: list[GatewayMailAttachment]
    gold: int


class GatewayMailList(BaseModel):
    mails: list[GatewayMailView]


class GatewayMailDetail(GatewayMailView):
    content: str


class GatewayMailClaim(BaseModel):
    """What one claim added. A repeat claim returns the same props/gold with replayed=true and
    adds nothing; items and currencies are the current counts either way."""

    props: list[GatewayMailAttachment]
    gold: int
    items: list[GatewayItemView]
    currencies: dict[str, int]
    replayed: bool = False


class AdminMailSend(BaseModel):
    account_ids: list[Annotated[str, Field(min_length=1, max_length=36)]] = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=64)
    content: str = Field(default="", max_length=2000)
    sender: str = Field(default="System", min_length=1, max_length=32)
    attachments: list[GatewayMailAttachment] = Field(default_factory=list, max_length=MAIL_ATTACHMENTS)
    gold: int = Field(default=0, ge=0, le=10_000_000)
    deadline_days: int = Field(default=30, ge=1, le=365)
    reason: str = Field(min_length=3, max_length=240)


class AdminMailSent(BaseModel):
    account_id: str
    mail_id: int


class AdminMailSendResult(BaseModel):
    sent: list[AdminMailSent]
    skipped: list[str]


class AdminMailView(GatewayMailDetail):
    account_id: str
    deleted: bool
    expired: bool
    sent_by: str | None
    read_at: datetime | None
    claimed_at: datetime | None
    deleted_at: datetime | None


# ---- Gateway servers (original-client server-select screen) -------------------------------------

SERVER_KEY_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,31}$"
# One token in the client's space-separated server list line (UILogin.parseOneServerInfo).
SERVER_NAME_PATTERN = r"^[A-Za-z0-9_.-]{1,32}$"
SERVER_STATUS_PATTERN = r"^(auto|smooth|busy|full|maintenance)$"


class GatewayServerHeartbeat(BaseModel):
    """What one gateway process reports every few seconds. `name` is used only when the server is
    first registered; after that the operator's name wins."""

    server_key: str = Field(pattern=SERVER_KEY_PATTERN)
    name: str = Field(default="Private-Server", pattern=SERVER_NAME_PATTERN)
    host: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.:-]+$")
    port: int = Field(ge=1, le=65535)
    version: str = Field(default="", max_length=64)
    players_online: int = Field(default=0, ge=0, le=100_000)
    players_in_match: int = Field(default=0, ge=0, le=100_000)
    started_at: datetime | None = None


class GatewayServerEntry(BaseModel):
    """One row of the client's server list. `status` is the effective state (auto resolved)."""

    server_key: str
    name: str
    host: str
    port: int
    zone: int
    group_id: int
    status: str
    listed: bool


class GatewayServerList(BaseModel):
    servers: list[GatewayServerEntry]


class AdminGameServer(GatewayServerEntry):
    configured_status: str
    capacity: int
    version: str
    live: bool
    players_online: int
    players_in_match: int
    started_at: datetime | None
    last_seen_at: datetime | None


class AdminGameServerList(BaseModel):
    servers: list[AdminGameServer]
    players_online: int
    players_in_match: int


class AdminGameServerUpdate(BaseModel):
    name: str | None = Field(default=None, pattern=SERVER_NAME_PATTERN)
    status: str | None = Field(default=None, pattern=SERVER_STATUS_PATTERN)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    listed: bool | None = None
    zone: int | None = Field(default=None, ge=0, le=1000)
    reason: str = Field(min_length=3, max_length=240)

"""Messages between the original-client gateway and this server."""

from datetime import datetime

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
    # Lobby theme (hall background) prop id; 0 keeps the client default.
    theme: int = Field(default=0, ge=0)


class GatewayState(BaseModel):
    """What the gateway needs at login: diamonds, owned appearance items, worn outfit."""

    yuanbao: int
    items: list[GatewayItemView]
    outfit: GatewayOutfit
    head_frame: int = 0


class GatewayPurchaseRequest(BaseModel):
    """Pay `price` diamonds (0 for draws paid in other client currencies) and add `props`."""

    price: int = Field(ge=0, le=1_000_000)
    props: list[int] = PROP_IDS
    reason: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_.:-]+$")


class GatewayPurchaseResult(BaseModel):
    yuanbao: int
    added: list[int]


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


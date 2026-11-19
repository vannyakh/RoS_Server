"""Messages between the original-client gateway and this server."""

from pydantic import BaseModel, Field

EXTERNAL_UID_PATTERN = r"^[0-9A-Za-z_.\-]{1,64}$"


class GatewayResolveRequest(BaseModel):
    external_uid: str = Field(pattern=EXTERNAL_UID_PATTERN)
    ip_address: str | None = Field(default=None, max_length=64)


class GatewayCharacterRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=32)
    char_type: int = Field(ge=0)


PORTRAIT_PATTERN = r"^[0-9A-Za-z_.\-]{0,128}$"


class GatewayPortraitRequest(BaseModel):
    portrait: str = Field(pattern=PORTRAIT_PATTERN)


class GatewayAccount(BaseModel):
    account_id: str
    username: str
    status: str
    can_play: bool
    is_new: bool
    nickname: str
    char_type: int | None
    portrait: str = ""


PROP_IDS = Field(default_factory=list, max_length=200)


class GatewayItemView(BaseModel):
    prop_id: int
    number: int


class GatewayOutfit(BaseModel):
    body: list[int] = Field(default_factory=list, max_length=64)
    wear: list[int] = Field(default_factory=list, max_length=64)


class GatewayState(BaseModel):
    """What the gateway needs at login: diamonds, owned appearance items, worn outfit."""

    yuanbao: int
    items: list[GatewayItemView]
    outfit: GatewayOutfit


class GatewayPurchaseRequest(BaseModel):
    """Pay `price` diamonds (0 for draws paid in other client currencies) and add `props`."""

    price: int = Field(ge=0, le=1_000_000)
    props: list[int] = PROP_IDS
    reason: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_.:-]+$")


class GatewayPurchaseResult(BaseModel):
    yuanbao: int
    added: list[int]


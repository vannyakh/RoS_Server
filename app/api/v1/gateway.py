"""Routes the original-client gateway (bigworld_gateway/) calls. Protected by a shared key."""

import hmac

from fastapi import APIRouter, Depends, Header, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.infrastructure.database import get_db
from app.schemas.gateway import (
    EXTERNAL_UID_PATTERN,
    GatewayAccount,
    GatewayCharacterRequest,
    GatewayCreditClaim,
    GatewayMatchReport,
    GatewayOutfit,
    GatewayProfile,
    GatewayPurchaseRequest,
    GatewayPurchaseResult,
    GatewayState,
    GatewayPortraitRequest,
    GatewayPresence,
    GatewayResolveRequest,
)
from app.services.gateway_profile_service import GatewayProfileService
from app.services.gateway_service import GatewayService

router = APIRouter(prefix="/gateway", tags=["Gateway"])


def require_gateway_key(x_gateway_key: str | None = Header(default=None)) -> None:
    expected = settings.gateway_api_key
    if not expected:
        raise AppError(404, "Not Found")
    if not x_gateway_key or not hmac.compare_digest(x_gateway_key.encode(), expected.encode()):
        raise AppError(401, "Invalid gateway key")


@router.post("/accounts/resolve", response_model=GatewayAccount, dependencies=[Depends(require_gateway_key)])
async def resolve_account(body: GatewayResolveRequest, db: AsyncSession = Depends(get_db)) -> GatewayAccount:
    return await GatewayService(db).resolve(body.external_uid, body.ip_address, body.device)


@router.put(
    "/accounts/{external_uid}/character",
    response_model=GatewayAccount,
    dependencies=[Depends(require_gateway_key)],
)
async def set_character(
    body: GatewayCharacterRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayAccount:
    return await GatewayService(db).set_character(external_uid, body.nickname, body.char_type)


@router.put(
    "/accounts/{external_uid}/portrait",
    response_model=GatewayAccount,
    dependencies=[Depends(require_gateway_key)],
)
async def set_portrait(
    body: GatewayPortraitRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayAccount:
    return await GatewayService(db).set_portrait(external_uid, body.portrait)


@router.get(
    "/accounts/{external_uid}/state",
    response_model=GatewayState,
    dependencies=[Depends(require_gateway_key)],
)
async def get_state(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayState:
    return await GatewayService(db).state(external_uid)


@router.post(
    "/accounts/{external_uid}/purchase",
    response_model=GatewayPurchaseResult,
    dependencies=[Depends(require_gateway_key)],
)
async def purchase(
    body: GatewayPurchaseRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayPurchaseResult:
    return await GatewayService(db).purchase(external_uid, body.price, body.props, body.reason)


@router.put(
    "/accounts/{external_uid}/outfit",
    response_model=GatewayOutfit,
    dependencies=[Depends(require_gateway_key)],
)
async def set_outfit(
    body: GatewayOutfit,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayOutfit:
    return await GatewayService(db).set_outfit(external_uid, body)


@router.get(
    "/accounts/{external_uid}/profile",
    response_model=GatewayProfile,
    dependencies=[Depends(require_gateway_key)],
)
async def get_profile(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayProfile:
    return await GatewayProfileService(db).profile(external_uid)


@router.post(
    "/accounts/{external_uid}/matches",
    response_model=GatewayProfile,
    dependencies=[Depends(require_gateway_key)],
)
async def record_match(
    body: GatewayMatchReport,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayProfile:
    return await GatewayProfileService(db).record_match(external_uid, body)


@router.post(
    "/accounts/{external_uid}/credit/claim",
    response_model=GatewayCreditClaim,
    dependencies=[Depends(require_gateway_key)],
)
async def claim_credit_reward(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayCreditClaim:
    return await GatewayProfileService(db).claim_credit_reward(external_uid)


@router.post(
    "/accounts/{external_uid}/presence",
    response_model=GatewayPresence,
    dependencies=[Depends(require_gateway_key)],
)
async def report_presence(
    body: GatewayPresence,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayPresence:
    return GatewayPresence(online=await GatewayService(db).report_presence(external_uid, body.online))

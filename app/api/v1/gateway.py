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
    GatewayOutfit,
    GatewayPurchaseRequest,
    GatewayPurchaseResult,
    GatewayState,
    GatewayPortraitRequest,
    GatewayResolveRequest,
)
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
    return await GatewayService(db).resolve(body.external_uid, body.ip_address)


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

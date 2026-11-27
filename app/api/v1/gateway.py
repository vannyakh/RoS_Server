"""Routes the original-client gateway (bigworld_gateway/) calls. Protected by a shared key."""

import hmac

from fastapi import APIRouter, Depends, Header, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.infrastructure.database import get_db
from app.schemas.gateway import (
    EXTERNAL_UID_PATTERN,
    GatewayAccount,
    GatewayCharacterRequest,
    GatewayCompoundRequest,
    GatewayCompoundResult,
    GatewayDevGrantRequest,
    GatewayCreditClaim,
    GatewayMatchReport,
    GatewayOutfit,
    GatewayProfile,
    GatewayPurchaseRequest,
    GatewayPurchaseResult,
    GatewayTopupRequest,
    GatewayTopupResult,
    GatewayState,
    GatewayNationalFlagRequest,
    GatewayHeadFrameRequest,
    GatewayPortraitRequest,
    GatewayPresence,
    GatewayResolveRequest,
)
from app.services.gateway_profile_service import GatewayProfileService
from app.services.gateway_service import GatewayService
from app.services.store_listing_service import StoreListingService
from app.schemas.gateway import GatewayMailClaim, GatewayMailDetail, GatewayMailList
from app.services.gateway_mail_service import GatewayMailService

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


@router.put(
    "/accounts/{external_uid}/head-frame",
    response_model=GatewayAccount,
    dependencies=[Depends(require_gateway_key)],
)
async def set_head_frame(
    body: GatewayHeadFrameRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayAccount:
    return await GatewayService(db).set_head_frame(external_uid, body.head_frame)


@router.put(
    "/accounts/{external_uid}/national-flag",
    response_model=GatewayAccount,
    dependencies=[Depends(require_gateway_key)],
)
async def set_national_flag(
    body: GatewayNationalFlagRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayAccount:
    return await GatewayService(db).set_national_flag(external_uid, body.national_flag)


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
    response_model_exclude_unset=True,  # `replayed` only when the request carried a request_id
    dependencies=[Depends(require_gateway_key)],
)
async def purchase(
    body: GatewayPurchaseRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayPurchaseResult:
    """With `request_id`, a repeat replays the first result (replayed=true) and charges nothing;
    the same id with a different price or props answers 409 {"code": "request_id_reused"}."""
    return await GatewayService(db).purchase(
        external_uid, body.price, body.props, body.reason, request_id=body.request_id
    )


@router.post(
    "/accounts/{external_uid}/topup",
    response_model=GatewayTopupResult,
    dependencies=[Depends(require_gateway_key)],
)
async def topup(
    body: GatewayTopupRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayTopupResult:
    """Credit diamonds (private IAP). The same reference is applied once per player (replayed=true)."""
    return await GatewayService(db).topup_yuanbao(external_uid, body.amount, body.reference, body.reason)


@router.post(
    "/accounts/{external_uid}/workshop/compound",
    response_model=GatewayCompoundResult,
    dependencies=[Depends(require_gateway_key)],
)
async def workshop_compound(
    body: GatewayCompoundRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayCompoundResult:
    """Depot > Workshop upgrade. 409 {"code": "insufficient", "missing": [...]} changes nothing."""
    return await GatewayService(db).compound(external_uid, body)


@router.post(
    "/accounts/{external_uid}/dev/grant",
    response_model=GatewayState,
    dependencies=[Depends(require_gateway_key)],
)
async def dev_grant(
    body: GatewayDevGrantRequest,
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayState:
    """Development only: add props and gold. 404 unless APP_ENV is development."""
    if settings.app_env != "development":
        raise AppError(404, "Not Found")
    return await GatewayService(db).dev_grant(external_uid, body.props, body.currencies)


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


@router.get("/store/listings", dependencies=[Depends(require_gateway_key)])
async def store_listings(db: AsyncSession = Depends(get_db)) -> dict:
    """Operator overrides of in-game store listings (lobby themes). Items not listed keep the
    client's own mall price."""
    return {"listings": await StoreListingService(db).gateway_listings()}


MAIL_ID = Path(ge=1, le=2_147_483_647)


@router.get(
    "/accounts/{external_uid}/mails",
    response_model=GatewayMailList,
    dependencies=[Depends(require_gateway_key)],
)
async def list_mails(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    db: AsyncSession = Depends(get_db),
) -> GatewayMailList:
    """System mail, newest first. Deleted and expired mail is left out."""
    return GatewayMailList(mails=await GatewayMailService(db).mails(external_uid))


@router.get(
    "/accounts/{external_uid}/mails/{mail_id}",
    response_model=GatewayMailDetail,
    dependencies=[Depends(require_gateway_key)],
)
async def mail_detail(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    mail_id: int = MAIL_ID,
    db: AsyncSession = Depends(get_db),
) -> GatewayMailDetail:
    """One mail with its content; marks it read."""
    return await GatewayMailService(db).detail(external_uid, mail_id)


@router.post(
    "/accounts/{external_uid}/mails/{mail_id}/claim",
    response_model=GatewayMailClaim,
    dependencies=[Depends(require_gateway_key)],
)
async def claim_mail(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    mail_id: int = MAIL_ID,
    db: AsyncSession = Depends(get_db),
) -> GatewayMailClaim:
    """Add the attachments and gold once. A repeat claim answers replayed=true and adds nothing."""
    return await GatewayMailService(db).claim(external_uid, mail_id)


@router.delete(
    "/accounts/{external_uid}/mails/{mail_id}",
    status_code=204,
    dependencies=[Depends(require_gateway_key)],
)
async def delete_mail(
    external_uid: str = Path(pattern=EXTERNAL_UID_PATTERN),
    mail_id: int = MAIL_ID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft delete. Attachments that were not claimed are forfeited."""
    await GatewayMailService(db).delete(external_uid, mail_id)
    return Response(status_code=204)

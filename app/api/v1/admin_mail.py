"""Operator system mail to original-client players (RO-117)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import current_operator
from app.infrastructure.database import get_db
from app.schemas.gateway import AdminMailSend, AdminMailSendResult, AdminMailView
from app.services.gateway_mail_service import GatewayMailService
from app.services.operator_service import OperatorActor

router = APIRouter(prefix="/admin/mails", tags=["Mail"])


@router.post("", response_model=AdminMailSendResult, status_code=201)
async def send_mail(
    body: AdminMailSend,
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> AdminMailSendResult:
    """One mail per account that has a gateway identity (permission players.economy).
    Accounts without one are returned in `skipped`."""
    return await GatewayMailService(db).send(actor, body)


@router.get("")
async def list_mails(
    account_id: str = Query(min_length=1, max_length=36),
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[AdminMailView]]:
    """Every mail of one account, including claimed, deleted and expired (permission players.read)."""
    return {"mails": await GatewayMailService(db).list_for_account(actor, account_id)}

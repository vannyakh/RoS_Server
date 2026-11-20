"""Store administration: ledger, spend summary, skin catalog, top-up and refund."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import current_operator, require
from app.infrastructure.database import get_db
from app.schemas.common import Page
from app.services.operator_service import OperatorActor
from app.services.store_service import StoreService

router = APIRouter(prefix="/admin/store", tags=["Store"])


class TopUp(BaseModel):
    account_id: str
    currency: str = Field(min_length=1, max_length=16)
    amount: int = Field(gt=0, le=10_000_000)
    reference: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=3, max_length=240)


class Refund(BaseModel):
    transaction_id: str
    reason: str = Field(min_length=3, max_length=240)


@router.get("/ledger", response_model=Page[dict])
async def ledger(
    start: date | None = None,
    end: date | None = None,
    currency: str | None = Query(default=None, max_length=16),
    kind: str | None = Query(default=None, pattern="^(purchase|draw|topup|refund|grant|admin)$"),
    q: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: OperatorActor = Depends(require("store.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[dict]:
    items, total = await StoreService(db).ledger(actor, first=start, last=end, currency=currency, kind=kind, query=q, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/summary")
async def summary(
    start: date | None = None,
    end: date | None = None,
    days: int = Query(default=30, ge=1, le=366),
    actor: OperatorActor = Depends(require("store.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await StoreService(db).summary(actor, first=start, last=end, days=days)


@router.get("/catalog")
async def catalog(actor: OperatorActor = Depends(require("store.read")), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await StoreService(db).catalog(actor)


@router.post("/topup", status_code=201)
async def topup(body: TopUp, actor: OperatorActor = Depends(current_operator), db: AsyncSession = Depends(get_db)) -> dict:
    return await StoreService(db).topup(actor, body.account_id, body.currency, body.amount, body.reference, body.reason)


@router.post("/refund", status_code=201)
async def refund(body: Refund, actor: OperatorActor = Depends(current_operator), db: AsyncSession = Depends(get_db)) -> dict:
    return await StoreService(db).refund(actor, body.transaction_id, body.reason)

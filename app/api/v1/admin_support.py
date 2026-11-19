"""Support cases, reports, and the player record those permissions can read."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import current_operator, require
from app.infrastructure.database import get_db
from app.schemas.common import Page
from app.services.operator_service import OperatorActor
from app.services.support_service import SupportService

router = APIRouter(prefix="/admin", tags=["Support"])


class AccountAction(BaseModel):
    action: str = Field(pattern="^(suspend|reactivate|ban|unban|note)$")
    reason: str = Field(min_length=3, max_length=240)


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=32)
    char_type: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3, max_length=240)


class CaseCreate(BaseModel):
    account_id: str
    subject: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    category: str
    priority: str = "normal"


class CaseUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assignee_id: str | None = None
    resolution: str | None = Field(default=None, max_length=240)


class CaseNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    visibility: str = "internal"


class ReportCreate(BaseModel):
    reported_account_id: str
    reporter_account_id: str | None = None
    match_id: str | None = None
    category: str
    description: str = Field(min_length=1, max_length=4000)


class ReportUpdate(BaseModel):
    status: str | None = None
    assignee_id: str | None = None
    resolution: str | None = Field(default=None, max_length=240)


@router.get("/dashboard")
async def dashboard(actor: OperatorActor = Depends(require("dashboard.read")), db: AsyncSession = Depends(get_db)) -> dict:
    return await SupportService(db).dashboard(actor)


@router.get("/players/{account_id}")
async def player(account_id: str, actor: OperatorActor = Depends(require("players.read")), db: AsyncSession = Depends(get_db)) -> dict:
    return await SupportService(db).player(actor, account_id)


@router.patch("/players/{account_id}/profile")
async def update_player_profile(
    account_id: str,
    body: ProfileUpdate,
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).update_profile(actor, account_id, body.nickname, body.char_type, body.reason)


@router.post("/players/{account_id}/actions")
async def player_action(
    account_id: str,
    body: AccountAction,
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).act(actor, account_id, body.action, body.reason)


@router.get("/support")
async def support_cases(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=64),
    status: str | None = None,
    actor: OperatorActor = Depends(require("support.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[dict]:
    items, total = await SupportService(db).cases(actor, limit, offset, q, status)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/support", status_code=201)
async def create_support_case(
    body: CaseCreate,
    actor: OperatorActor = Depends(require("support.write")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).create_case(actor, body.account_id, body.subject, body.description, body.category, body.priority)


@router.get("/support/{case_id}")
async def support_case(case_id: str, actor: OperatorActor = Depends(require("support.read")), db: AsyncSession = Depends(get_db)) -> dict:
    return await SupportService(db).case(actor, case_id)


@router.patch("/support/{case_id}")
async def update_support_case(
    case_id: str,
    body: CaseUpdate,
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).update_case(actor, case_id, body.model_dump(exclude_unset=True))


@router.post("/support/{case_id}/notes", status_code=201)
async def add_support_note(
    case_id: str,
    body: CaseNoteCreate,
    actor: OperatorActor = Depends(require("support.write")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).add_case_note(actor, case_id, body.body, body.visibility)


@router.get("/reports")
async def reports(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    actor: OperatorActor = Depends(require("reports.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[dict]:
    items, total = await SupportService(db).reports(actor, limit, offset, status)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/reports", status_code=201)
async def create_report(
    body: ReportCreate,
    actor: OperatorActor = Depends(require("reports.review")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).create_report(
        actor,
        body.reported_account_id,
        body.category,
        body.description,
        body.reporter_account_id,
        body.match_id,
    )


@router.get("/reports/{report_id}")
async def report(report_id: str, actor: OperatorActor = Depends(require("reports.read")), db: AsyncSession = Depends(get_db)) -> dict:
    return await SupportService(db).report(actor, report_id)


@router.patch("/reports/{report_id}")
async def update_report(
    report_id: str,
    body: ReportUpdate,
    actor: OperatorActor = Depends(require("reports.review")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await SupportService(db).update_report(actor, report_id, body.model_dump(exclude_unset=True))


@router.get("/lobbies")
async def stored_lobbies(actor: OperatorActor = Depends(require("lobbies.read")), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await SupportService(db).lobbies(actor)


@router.get("/lobbies/{lobby_id}")
async def stored_lobby(lobby_id: str, actor: OperatorActor = Depends(require("lobbies.read")), db: AsyncSession = Depends(get_db)) -> dict:
    return await SupportService(db).lobby(actor, lobby_id)


@router.get("/match-records")
async def stored_matches(actor: OperatorActor = Depends(require("matches.read")), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await SupportService(db).matches(actor)


@router.get("/match-records/{match_id}")
async def stored_match(match_id: str, actor: OperatorActor = Depends(require("matches.read")), db: AsyncSession = Depends(get_db)) -> dict:
    return await SupportService(db).match(actor, match_id)

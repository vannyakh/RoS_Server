"""Operator sign-in, roles, and the records those permissions can read."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import bearer
from app.core.exceptions import AppError
from app.infrastructure.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import Page
from app.services.operator_service import OperatorActor, OperatorService

router = APIRouter(prefix="/admin", tags=["Administration"])


class OperatorCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)
    roles: list[str] = Field(default_factory=list)


class RoleCreate(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=160)


class PermissionUpdate(BaseModel):
    permissions: list[str]


class RoleUpdate(BaseModel):
    roles: list[str]


class PlayerStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|closed)$")


async def current_operator(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> OperatorActor:
    return await OperatorService(db).actor_for_token(credentials.credentials)


def require(permission: str):
    async def dependency(actor: OperatorActor = Depends(current_operator)) -> OperatorActor:
        if permission not in actor.permissions:
            raise AppError(403, "Permission denied")
        return actor

    return dependency


@router.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await OperatorService(db).login(data.username, data.password)


@router.post("/auth/logout", status_code=204)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> None:
    await OperatorService(db).revoke(actor.operator.id, credentials.credentials)


@router.get("/me")
async def me(actor: OperatorActor = Depends(current_operator)) -> dict:
    return {
        "id": actor.operator.id,
        "username": actor.operator.username,
        "status": actor.operator.status,
        "roles": actor.role_codes,
        "permissions": sorted(actor.permissions),
    }


@router.get("/players")
async def players(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, pattern="^(active|suspended|closed)$"),
    client: str | None = Query(default=None, pattern="^(game|web)$"),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    _actor: OperatorActor = Depends(require("players.read")),
    db: AsyncSession = Depends(get_db),
) -> Page[dict]:
    items, total = await OperatorService(db).players(
        limit, offset, q, status, client=client, created_from=created_from, created_to=created_to
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.patch("/players/{account_id}")
async def set_player_status(
    account_id: str,
    body: PlayerStatusUpdate,
    actor: OperatorActor = Depends(require("players.manage")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await OperatorService(db).set_player_status(actor, account_id, body.status)


@router.get("/operators")
async def operators(
    _actor: OperatorActor = Depends(require("operators.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await OperatorService(db).operators()


@router.post("/operators", status_code=201)
async def create_operator(
    body: OperatorCreate,
    actor: OperatorActor = Depends(require("operators.create")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    created = await OperatorService(db).create_operator(body.username, body.password, body.roles, actor=actor)
    return {"id": created.id, "username": created.username}


@router.patch("/operators/{operator_id}")
async def set_operator_status(
    operator_id: str,
    body: PlayerStatusUpdate,
    actor: OperatorActor = Depends(require("operators.manage")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.status not in {"active", "suspended"}:
        raise AppError(422, "Operator status must be active or suspended")
    return await OperatorService(db).set_operator_status(actor, operator_id, body.status)


@router.put("/operators/{operator_id}/roles")
async def set_operator_roles(
    operator_id: str,
    body: RoleUpdate,
    actor: OperatorActor = Depends(require("roles.assign")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    roles = await OperatorService(db).set_operator_roles(actor, operator_id, body.roles)
    return {"id": operator_id, "roles": roles}


@router.get("/roles")
async def roles(
    _actor: OperatorActor = Depends(require("roles.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await OperatorService(db).roles()


@router.get("/permissions")
async def permissions(
    _actor: OperatorActor = Depends(require("roles.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await OperatorService(db).permissions()


@router.post("/roles", status_code=201)
async def create_role(
    body: RoleCreate,
    actor: OperatorActor = Depends(require("roles.create")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    created = await OperatorService(db).create_role(actor, body.code, body.name, body.description)
    return {"id": created.id, "code": created.code, "name": created.name}


@router.put("/roles/{role_id}/permissions")
async def set_role_permissions(
    role_id: str,
    body: PermissionUpdate,
    actor: OperatorActor = Depends(require("roles.assign")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    codes = await OperatorService(db).set_role_permissions(actor, role_id, body.permissions)
    return {"id": role_id, "permissions": codes}


@router.get("/audit")
async def audit(
    limit: int = Query(default=100, ge=1, le=200),
    _actor: OperatorActor = Depends(require("logs.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await OperatorService(db).audit(limit)


@router.get("/logs")
async def logs(
    limit: int = Query(default=200, ge=1, le=400),
    _actor: OperatorActor = Depends(require("logs.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return {"lines": OperatorService(db).server_log(limit)}

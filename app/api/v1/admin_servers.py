"""Operator view and controls for original-client gateway servers (Game servers page)."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import current_operator
from app.infrastructure.database import get_db
from app.schemas.gateway import SERVER_KEY_PATTERN, AdminGameServer, AdminGameServerList, AdminGameServerUpdate
from app.services.game_server_service import GameServerService
from app.services.operator_service import OperatorActor

router = APIRouter(prefix="/admin/game-servers", tags=["Game servers"])


@router.get("", response_model=AdminGameServerList)
async def list_game_servers(
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> AdminGameServerList:
    """Every registered gateway with live state and player counts (permission servers.read)."""
    return await GameServerService(db).admin_list(actor)


@router.patch("/{server_key}", response_model=AdminGameServer)
async def update_game_server(
    body: AdminGameServerUpdate,
    server_key: str = Path(pattern=SERVER_KEY_PATTERN),
    actor: OperatorActor = Depends(current_operator),
    db: AsyncSession = Depends(get_db),
) -> AdminGameServer:
    """Change name, status, capacity, zone or listed (permission servers.manage). Audited."""
    return await GameServerService(db).update(actor, server_key, body)

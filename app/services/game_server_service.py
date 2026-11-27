"""Original-client gateway servers: heartbeats from each gateway process, the list the game shows
on its server-select screen, and the operator controls (name, status, capacity, listed)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.gateway import GatewayServer
from app.models.types import utc_now
from app.observability.metrics import GATEWAY_PLAYERS_IN_MATCH, GATEWAY_PLAYERS_ONLINE, GATEWAY_SERVERS_LIVE
from app.schemas.gateway import (
    AdminGameServer,
    AdminGameServerList,
    AdminGameServerUpdate,
    GatewayServerEntry,
    GatewayServerHeartbeat,
    GatewayServerList,
)
from app.services.operator_service import OperatorActor, OperatorService

# A gateway heartbeats every 10 s; three missed beats and it counts as down.
HEARTBEAT_LIVE_SECONDS = 30
BUSY_RATIO, FULL_RATIO = 0.6, 0.95


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_live(server: GatewayServer, now: datetime) -> bool:
    seen = _aware(server.last_seen_at)
    return seen is not None and now - seen <= timedelta(seconds=HEARTBEAT_LIVE_SECONDS)


def effective_status(server: GatewayServer, now: datetime) -> str:
    """Operator status wins; "auto" is maintenance while down, else load against capacity."""
    if server.status != "auto":
        return server.status
    if not is_live(server, now):
        return "maintenance"
    load = server.players_online / max(server.capacity, 1)
    if load >= FULL_RATIO:
        return "full"
    if load >= BUSY_RATIO:
        return "busy"
    return "smooth"


def _entry(server: GatewayServer, now: datetime) -> dict:
    return {
        "server_key": server.server_key,
        "name": server.name,
        "host": server.host,
        "port": server.port,
        "zone": server.zone,
        "group_id": server.group_id,
        "status": effective_status(server, now),
        "listed": server.listed,
    }


class GameServerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operators = OperatorService(session)

    # Gateway side ---------------------------------------------------------------------------

    async def heartbeat(self, body: GatewayServerHeartbeat) -> GatewayServerEntry:
        now = utc_now()
        server = await self._get(body.server_key)
        if server is None:
            server = GatewayServer(server_key=body.server_key, name=body.name, host=body.host, port=body.port)
            self.session.add(server)
        server.host, server.port, server.version = body.host, body.port, body.version
        server.players_online, server.players_in_match = body.players_online, body.players_in_match
        server.started_at = body.started_at or server.started_at
        server.last_seen_at = now
        await self.session.commit()
        await self._update_gauges(now)
        return GatewayServerEntry(**_entry(server, now))

    async def client_list(self) -> GatewayServerList:
        """Listed servers for the game's server-select screen, in a stable order."""
        now = utc_now()
        rows = await self.session.scalars(
            select(GatewayServer).where(GatewayServer.listed.is_(True)).order_by(GatewayServer.zone, GatewayServer.server_key)
        )
        return GatewayServerList(servers=[GatewayServerEntry(**_entry(row, now)) for row in rows])

    # Operator side --------------------------------------------------------------------------

    async def admin_list(self, actor: OperatorActor) -> AdminGameServerList:
        self.operators._need(actor, "servers.read")
        now = utc_now()
        rows = list(await self.session.scalars(select(GatewayServer).order_by(GatewayServer.zone, GatewayServer.server_key)))
        servers = [self._admin_view(row, now) for row in rows]
        live = [s for s in servers if s.live]
        return AdminGameServerList(
            servers=servers,
            players_online=sum(s.players_online for s in live),
            players_in_match=sum(s.players_in_match for s in live),
        )

    async def update(self, actor: OperatorActor, server_key: str, body: AdminGameServerUpdate) -> AdminGameServer:
        self.operators._need(actor, "servers.manage")
        server = await self._get(server_key)
        if server is None:
            raise AppError(404, "Game server was not found")
        changes = body.model_dump(exclude_unset=True, exclude={"reason"})
        changes = {k: v for k, v in changes.items() if v is not None and getattr(server, k) != v}
        if not changes:
            return self._admin_view(server, utc_now())
        detail = ", ".join(f"{k} {getattr(server, k)!r} -> {v!r}" for k, v in sorted(changes.items()))
        for key, value in changes.items():
            setattr(server, key, value)
        await self.operators._audit(actor, "server.update", "game_server", server_key, detail, body.reason.strip())
        await self.session.commit()
        return self._admin_view(server, utc_now())

    # Helpers --------------------------------------------------------------------------------

    def _admin_view(self, server: GatewayServer, now: datetime) -> AdminGameServer:
        live = is_live(server, now)
        return AdminGameServer(
            **_entry(server, now),
            configured_status=server.status,
            capacity=server.capacity,
            version=server.version,
            live=live,
            players_online=server.players_online if live else 0,
            players_in_match=server.players_in_match if live else 0,
            started_at=server.started_at,
            last_seen_at=server.last_seen_at,
        )

    async def _get(self, server_key: str) -> GatewayServer | None:
        return await self.session.scalar(select(GatewayServer).where(GatewayServer.server_key == server_key))

    async def _update_gauges(self, now: datetime) -> None:
        rows = [row for row in await self.session.scalars(select(GatewayServer)) if is_live(row, now)]
        GATEWAY_SERVERS_LIVE.set(len(rows))
        GATEWAY_PLAYERS_ONLINE.set(sum(row.players_online for row in rows))
        GATEWAY_PLAYERS_IN_MATCH.set(sum(row.players_in_match for row in rows))

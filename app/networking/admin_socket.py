"""Operator live feed over WebSocket.

The first message must be {"type": "auth", "payload": {"token": "<operator access token>"}}.
The server then sends `auth.ok` (with the account ids now on the game socket), a `dashboard.snapshot` whenever the counts change (checked
every few seconds, operators with dashboard.read only), `player.presence` when a player opens
or closes the game socket, and `player.changed` after an operator edits a player (both need
players.read). The token is checked again on every snapshot tick, so a revoked or expired
token closes the socket with 4003. The client sends {"type": "ping"} and gets `pong`.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket
from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocketDisconnect

from app.core.exceptions import AppError
from app.game.engine import game_engine
from app.infrastructure.database import SessionLocal
from app.networking.admin_hub import AdminSubscriber, admin_hub
from app.networking.validation import MAX_MESSAGE_BYTES
from app.services.operator_service import OperatorActor, OperatorService
from app.services.support_service import SupportService

router = APIRouter()
logger = logging.getLogger(__name__)

AUTH_TIMEOUT = 5
IDLE_TIMEOUT = 60
SNAPSHOT_SECONDS = 5
FEED_PERMISSIONS = {"dashboard.read", "players.read", "matches.read"}
SPECTATE_SECONDS = 0.2
# Skip a frame rather than queue it when the browser is not keeping up.
SPECTATE_BACKLOG = 48


def _message(message_type: str, payload: dict) -> dict:
    return {"version": 1, "type": message_type, "payload": payload}


@router.websocket("/api/v1/admin/ws")
async def admin_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    token, actor = await _authenticate(websocket)
    if actor is None:
        return
    subscriber = admin_hub.subscribe(actor.operator.id, actor.permissions)
    await websocket.send_json(
        _message(
            "auth.ok",
            {
                "operator": actor.operator.username,
                "permissions": sorted(actor.permissions & FEED_PERMISSIONS),
                "online_players": admin_hub.online_players,
                "online_account_ids": admin_hub.online_ids() if "players.read" in actor.permissions else [],
            },
        )
    )
    tasks = [
        asyncio.create_task(_send_loop(websocket, subscriber)),
        asyncio.create_task(_snapshot_loop(subscriber, token)),
        asyncio.create_task(_receive_loop(websocket, subscriber)),
        asyncio.create_task(_spectate_loop(subscriber)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        admin_hub.unsubscribe(subscriber)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await _flush(websocket, subscriber)
        await _close(websocket, subscriber.close_code)


async def _authenticate(websocket: WebSocket) -> tuple[str, OperatorActor | None]:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT)
    except (asyncio.TimeoutError, RuntimeError, WebSocketDisconnect):
        await _close(websocket, 4001)
        return "", None
    message = _parse(raw)
    if message is None or message.get("type") != "auth":
        await websocket.send_json(_message("error", {"detail": "Authentication required"}))
        await _close(websocket, 4003)
        return "", None
    token = str((message.get("payload") or {}).get("token") or "")
    actor = await _actor(token)
    if actor is None or not actor.permissions & FEED_PERMISSIONS:
        await websocket.send_json(_message("error", {"detail": "Invalid or expired token"}))
        await _close(websocket, 4003)
        return "", None
    return token, actor


async def _actor(token: str) -> OperatorActor | None:
    if not token:
        return None
    try:
        async with SessionLocal() as session:
            return await OperatorService(session).actor_for_token(token)
    except AppError:
        return None
    except Exception as exc:
        logger.warning("Admin socket session lookup failed: %s", type(exc).__name__)
        return None


async def _send_loop(websocket: WebSocket, subscriber: AdminSubscriber) -> None:
    """The only writer after auth.ok, so sends never interleave."""
    while True:
        message = await subscriber.queue.get()
        if message is None:
            return
        try:
            await websocket.send_json(message)
        except (RuntimeError, WebSocketDisconnect):
            return


async def _snapshot_loop(subscriber: AdminSubscriber, token: str) -> None:
    last: dict | None = None
    while True:
        admin_hub.sweep()
        if subscriber.dropped:
            subscriber.close_code = 1013
            return
        actor = await _actor(token)
        if actor is None:
            subscriber.queue.put_nowait(_message("error", {"detail": "Invalid or expired token"}))
            subscriber.close_code = 4003
            return
        subscriber.permissions = set(actor.permissions)
        if "dashboard.read" in actor.permissions:
            async with SessionLocal() as session:
                counts = jsonable_encoder(await SupportService(session).dashboard(actor))
            counts["online_players"] = admin_hub.online_players
            if counts != last:
                last = counts
                _offer(subscriber, _message("dashboard.snapshot", counts))
        await asyncio.sleep(SNAPSHOT_SECONDS)


async def _spectate_loop(subscriber: AdminSubscriber) -> None:
    """While the operator watches, send `match.frame` five times a second."""
    while True:
        await asyncio.sleep(SPECTATE_SECONDS)
        watching = subscriber.watching
        if watching is None or "matches.read" not in subscriber.permissions:
            continue
        if subscriber.queue.qsize() > SPECTATE_BACKLOG:
            continue
        frame = await game_engine.spectate(None if watching == "*" else watching, subscriber.watch_tick, static=subscriber.watch_static)
        if subscriber.watching != watching:
            continue
        subscriber.watch_static = False
        subscriber.watch_tick = frame["tick"]
        _offer(subscriber, _message("match.frame", {"watching": watching, **frame}))


async def _receive_loop(websocket: WebSocket, subscriber: AdminSubscriber) -> None:
    while True:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=IDLE_TIMEOUT)
        except asyncio.TimeoutError:
            subscriber.close_code = 4004
            return
        except (RuntimeError, WebSocketDisconnect):
            return
        message = _parse(raw)
        if message is None:
            _offer(subscriber, _message("error", {"detail": "Invalid message"}))
            continue
        if message.get("type") == "watch":
            if "matches.read" not in subscriber.permissions:
                _offer(subscriber, _message("error", {"detail": "Watching matches needs matches.read"}))
                continue
            match_id = (message.get("payload") or {}).get("match_id")
            subscriber.watching = match_id if isinstance(match_id, str) and match_id else "*"
            subscriber.watch_static = True
            subscriber.watch_tick = 0
            continue
        if message.get("type") == "unwatch":
            subscriber.watching = None
            continue
        if message.get("type") == "ping":
            _offer(subscriber, _message("pong", {"online_players": admin_hub.online_players}))
            continue
        _offer(subscriber, _message("error", {"detail": "Unknown message type"}))


async def _flush(websocket: WebSocket, subscriber: AdminSubscriber) -> None:
    """Deliver what was queued before the socket closes, such as the reason for a 4003."""
    while not subscriber.queue.empty():
        message = subscriber.queue.get_nowait()
        try:
            await websocket.send_json(message)
        except (RuntimeError, WebSocketDisconnect):
            return


def _offer(subscriber: AdminSubscriber, message: dict) -> None:
    try:
        subscriber.queue.put_nowait(message)
    except asyncio.QueueFull:
        subscriber.dropped = True


def _parse(raw: str) -> dict | None:
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        return None
    try:
        message = json.loads(raw)
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


async def _close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        pass

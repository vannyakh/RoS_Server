"""Authenticated WebSocket session."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.exceptions import AppError
from app.game.engine import game_engine
from app.infrastructure.database import SessionLocal
from app.repositories.player_repository import PlayerRepository
from app.services.account_service import AccountService
from app.networking.connection_manager import connection_manager
from app.networking.protocol import format_error, parse_action, parse_input, parse_message
from app.networking.validation import MAX_MESSAGE_BYTES, RateLimiter, SequenceTracker

router = APIRouter()
logger = logging.getLogger(__name__)
_AUTH_TIMEOUT = 5
_IDLE_TIMEOUT = 15


@router.websocket("/api/v1/ws")
async def game_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    player_id = None
    try:
        identity = await _authenticate(websocket)
        if identity is None:
            return
        player_id, nickname, skin, auth_sequence = identity
        await connection_manager.connect(player_id, websocket)
        await game_engine.connect(player_id, nickname=nickname, skin=skin)
        await _session_loop(websocket, player_id, auth_sequence)
    finally:
        if player_id is not None:
            connection_manager.disconnect(player_id, websocket)
            await game_engine.disconnect(player_id)


async def _authenticate(websocket: WebSocket) -> tuple[str, str | None, str, int] | None:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=_AUTH_TIMEOUT)
    except (asyncio.TimeoutError, RuntimeError, WebSocketDisconnect):
        await websocket.close(code=4001)
        return None
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        await websocket.close(code=1009)
        return None
    try:
        message = parse_message(raw)
    except ValidationError:
        await websocket.send_json(format_error(0, "Invalid message"))
        await websocket.close(code=4002)
        return None
    if message.type != "auth":
        await websocket.send_json(format_error(message.sequence, "Authentication required"))
        await websocket.close(code=4003)
        return None
    token = str(message.payload.get("token") or "")
    identity = await _identity_for_token(token)
    if identity is None:
        await websocket.send_json(format_error(message.sequence, "Invalid or expired token"))
        await websocket.close(code=4003)
        return None
    player_id, nickname, skin = identity
    await websocket.send_json(
        {
            "version": 1,
            "type": "auth.ok",
            "sequence": message.sequence,
            "payload": {"player_id": player_id},
        }
    )
    return player_id, nickname, skin, message.sequence


async def _identity_for_token(token: str) -> tuple[str, str | None, str] | None:
    try:
        async with SessionLocal() as session:
            account = await AccountService(session).account_for_token(token)
            player = await PlayerRepository(session).by_account_id(account.id)
    except AppError:
        return None
    except Exception as exc:
        logger.warning("WebSocket session lookup failed: %s", type(exc).__name__)
        return None
    nickname = player.nickname if player and player.nickname else account.username
    skin = player.avatar_id if player and player.avatar_id else "recruit"
    return account.id, nickname, skin


async def _session_loop(websocket: WebSocket, player_id: str, auth_sequence: int) -> None:
    sequences = SequenceTracker()
    sequences.last = auth_sequence
    limiter = RateLimiter()
    while True:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_IDLE_TIMEOUT)
        except WebSocketDisconnect:
            return
        except asyncio.TimeoutError:
            try:
                await websocket.close(code=4004)
            except RuntimeError:
                return
            return
        except RuntimeError:
            return
        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            await websocket.close(code=1009)
            return
        try:
            message = parse_message(raw)
        except ValidationError:
            await websocket.send_json(format_error(0, "Invalid message"))
            continue
        if message.type == "auth":
            await websocket.send_json(format_error(message.sequence, "Already authenticated"))
            continue
        if not sequences.accept(message.sequence):
            await websocket.send_json(format_error(message.sequence, "Sequence out of order"))
            continue
        if not limiter.allow():
            await websocket.send_json(format_error(message.sequence, "Rate limit exceeded"))
            continue
        if message.type == "heartbeat":
            await websocket.send_json(
                {"version": 1, "type": "heartbeat", "sequence": message.sequence, "payload": {}}
            )
            continue
        if message.type == "lobby.join":
            if message.payload.get("mode") == "training":
                ok, detail = await game_engine.join_training(player_id)
            else:
                ok, detail = await game_engine.join_queue(player_id)
            await _ack(websocket, "lobby.join.ack", message.sequence, ok, detail)
            continue
        if message.type == "lobby.leave":
            ok, detail = await game_engine.leave_queue(player_id)
            await _ack(websocket, "lobby.leave.ack", message.sequence, ok, detail)
            continue
        if message.type == "match.forfeit":
            ok, detail = await game_engine.forfeit(player_id)
            await _ack(websocket, "match.forfeit.ack", message.sequence, ok, detail)
            continue
        if message.type == "player.action":
            try:
                action = parse_action(message.payload)
            except ValidationError:
                await websocket.send_json(format_error(message.sequence, "Invalid player action"))
                continue
            ok, detail = await game_engine.perform(player_id, action.action, action.loot_id, action.item_id)
            await _ack(websocket, "player.action.ack", message.sequence, ok, detail)
            continue
        try:
            move = parse_input(message.payload)
        except ValidationError:
            await websocket.send_json(format_error(message.sequence, "Invalid player input"))
            continue
        tick = await game_engine.set_input(player_id, move.move_x, move.move_y, move.aim_x, move.aim_y)
        await websocket.send_json(
            {
                "version": 1,
                "type": "player.input.ack",
                "sequence": message.sequence,
                "payload": {"tick": tick},
            }
        )


async def _ack(websocket: WebSocket, message_type: str, sequence: int, ok: bool, detail: str) -> None:
    await websocket.send_json(
        {
            "version": 1,
            "type": message_type,
            "sequence": sequence,
            "payload": {"ok": ok, "detail": detail},
        }
    )

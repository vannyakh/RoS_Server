"""Validate this server's versioned JSON messages. This is not an official RoS decoder."""

import json
from urllib.parse import SplitResult, parse_qs, urlsplit

from pydantic import ValidationError

from app.networking.protocol import (
    ClientMessage,
    PlayerAction,
    parse_action,
    parse_input,
    parse_message,
)
from app.networking.validation import MAX_MESSAGE_BYTES, SequenceTracker

WEBSOCKET_PATH = "/api/v1/ws"


def known_message_types() -> tuple[str, ...]:
    return tuple(ClientMessage.model_fields["type"].annotation.__args__)


def known_player_actions() -> tuple[str, ...]:
    return tuple(PlayerAction.model_fields["action"].annotation.__args__)


def validate_message(raw: str) -> dict:
    message, result = _parse_frame(raw)
    if message is None:
        return result
    if not _payload_ok(message):
        return {"ok": False, "error": "ValidationError"}
    return result


def validate_stream(raw_messages: list[str]) -> list[dict]:
    """Accept frames in session order.

    A frame is accepted only when its sequence is greater than the last accepted
    sequence. An envelope that parses still consumes its sequence when the
    payload is invalid, matching the live socket.
    """
    tracker = SequenceTracker()
    results: list[dict] = []
    for raw in raw_messages:
        message, result = _parse_frame(raw)
        if message is None:
            results.append(result)
            continue
        if not tracker.accept(message.sequence):
            results.append(
                {
                    "ok": False,
                    "error": "SequenceError",
                    "version": message.version,
                    "type": message.type,
                    "sequence": message.sequence,
                }
            )
            continue
        if not _payload_ok(message):
            results.append({"ok": False, "error": "ValidationError"})
            continue
        results.append(result)
    return results


def validate_auth_transport(url: str, raw: str) -> dict:
    """The access token belongs in the first auth payload, not in the WebSocket URL."""
    parsed = urlsplit(url)
    if parsed.path != WEBSOCKET_PATH:
        return {"ok": False, "error": "UnexpectedPath"}
    if _url_carries_token(parsed, ""):
        return {"ok": False, "error": "TokenInUrl"}
    result = validate_message(raw)
    if not result["ok"]:
        return result
    if result["type"] != "auth":
        return {
            "ok": False,
            "error": "AuthenticationRequired",
            "type": result["type"],
            "sequence": result["sequence"],
        }
    token = _auth_token(json.loads(raw).get("payload") or {})
    if _url_carries_token(parsed, token):
        return {"ok": False, "error": "TokenInUrl"}
    return result


def validate_input(payload: dict) -> dict:
    try:
        parsed = parse_input(payload)
    except ValidationError:
        return {"ok": False, "error": "ValidationError"}
    return {"ok": True, "move_x": parsed.move_x, "move_y": parsed.move_y}


def validate_action(payload: dict) -> dict:
    try:
        parsed = parse_action(payload)
    except ValidationError:
        return {"ok": False, "error": "ValidationError"}
    return {"ok": True, "action": parsed.action}


def _parse_frame(raw: str) -> tuple[ClientMessage | None, dict]:
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        return None, {"ok": False, "error": "MessageTooLarge"}
    try:
        message = parse_message(raw)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        return None, {"ok": False, "error": exc.__class__.__name__}
    return message, {
        "ok": True,
        "version": message.version,
        "type": message.type,
        "sequence": message.sequence,
    }


def _payload_ok(message: ClientMessage) -> bool:
    if message.type == "auth":
        return _auth_token(message.payload) != ""
    if message.type == "player.input":
        try:
            parse_input(message.payload)
        except ValidationError:
            return False
        return True
    if message.type == "player.action":
        try:
            parse_action(message.payload)
        except ValidationError:
            return False
        return True
    return True


def _auth_token(payload: dict) -> str:
    return str(payload.get("token") or "")


def _url_carries_token(parsed: SplitResult[str], token: str) -> bool:
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "token" in query:
        return True
    return bool(token) and token in parsed.query

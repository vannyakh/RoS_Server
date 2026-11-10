"""Validate this server's versioned JSON messages. This is not an official RoS decoder."""

import json

from pydantic import ValidationError

from app.networking.protocol import parse_action, parse_input, parse_message


def validate_message(raw: str) -> dict:
    try:
        message = parse_message(raw)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": exc.__class__.__name__}
    return {"ok": True, "type": message.type, "sequence": message.sequence}


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

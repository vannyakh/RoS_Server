"""Versioned client messages."""

from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class ClientMessage(BaseModel):
    version: Literal[1]
    type: Literal[
        "auth",
        "heartbeat",
        "player.input",
        "player.action",
        "lobby.join",
        "lobby.leave",
        "match.forfeit",
    ]
    sequence: int = Field(ge=0)
    payload: dict = Field(default_factory=dict)


class PlayerInput(BaseModel):
    move_x: float = Field(ge=-1, le=1)
    move_y: float = Field(ge=-1, le=1)
    aim_x: float = Field(default=0, ge=-1, le=1)
    aim_y: float = Field(default=0, ge=-1, le=1)


class PlayerAction(BaseModel):
    action: Literal["shoot", "reload", "pickup", "use", "equip", "jump", "discard", "board", "exit"]
    loot_id: str | None = Field(default=None, max_length=80)
    item_id: str | None = Field(default=None, max_length=32)


def parse_message(raw: str) -> ClientMessage:
    return ClientMessage.model_validate_json(raw)


def parse_input(payload: dict) -> PlayerInput:
    return PlayerInput.model_validate(payload)


def parse_action(payload: dict) -> PlayerAction:
    return PlayerAction.model_validate(payload)


def format_error(sequence: int, detail: str) -> dict:
    return {"version": 1, "type": "error", "sequence": sequence, "payload": {"detail": detail}}


__all__ = [
    "ClientMessage",
    "PlayerAction",
    "PlayerInput",
    "ValidationError",
    "format_error",
    "parse_action",
    "parse_input",
    "parse_message",
]

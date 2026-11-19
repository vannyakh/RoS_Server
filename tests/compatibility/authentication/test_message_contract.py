"""Evidence for this server's JSON message contract.

The samples are this server's contract. A passing test is not original Rules of
Survival compatibility. compatibility_status stays unknown.
"""

import json

import pytest

from tools.protocol_validator import (
    known_message_types,
    known_player_actions,
    validate_auth_transport,
    validate_message,
    validate_stream,
)

TOKEN = "sample-access-token"
WEBSOCKET_PATH = "/api/v1/ws"

VALID_PAYLOADS = {
    "auth": {"token": TOKEN},
    "heartbeat": {},
    "player.input": {"move_x": 1, "move_y": -1, "aim_x": 0, "aim_y": 1},
    "player.action": {"action": "shoot"},
    "lobby.join": {},
    "lobby.leave": {},
    "match.forfeit": {},
}

INVALID_PAYLOADS = {
    "auth": {},
    "heartbeat": [],
    "player.input": {"move_x": 2, "move_y": 0},
    "player.action": {"action": "fly"},
    "lobby.join": "room",
    "lobby.leave": 1,
    "match.forfeit": ["leave"],
}


def _frame(message_type: str, sequence: int, payload: object) -> str:
    return json.dumps(
        {"version": 1, "type": message_type, "sequence": sequence, "payload": payload}
    )


def test_messages_are_this_servers_contract():
    assert "this server's contract" in __doc__
    assert set(known_message_types()) == set(VALID_PAYLOADS)


def test_every_known_type_has_a_valid_and_invalid_payload():
    assert set(INVALID_PAYLOADS) == set(known_message_types())
    for index, message_type in enumerate(known_message_types()):
        valid = validate_message(_frame(message_type, index, VALID_PAYLOADS[message_type]))
        assert valid["ok"] is True
        assert valid["version"] == 1
        assert valid["type"] == message_type
        assert valid["sequence"] == index
        invalid = validate_message(_frame(message_type, index, INVALID_PAYLOADS[message_type]))
        assert invalid == {"ok": False, "error": "ValidationError"}


def test_each_player_action_name_is_accepted():
    for name in known_player_actions():
        result = validate_message(_frame("player.action", 1, {"action": name}))
        assert result["ok"] is True
        assert result["type"] == "player.action"


def test_unknown_version_is_rejected():
    raw = json.dumps({"version": 2, "type": "heartbeat", "sequence": 1, "payload": {}})
    assert validate_message(raw) == {"ok": False, "error": "ValidationError"}


def test_unknown_message_type_is_rejected():
    raw = json.dumps({"version": 1, "type": "unknown", "sequence": 1, "payload": {}})
    assert validate_message(raw) == {"ok": False, "error": "ValidationError"}


def test_numeric_message_type_is_rejected():
    raw = json.dumps({"version": 1, "type": 7, "sequence": 1, "payload": {}})
    assert validate_message(raw) == {"ok": False, "error": "ValidationError"}


def test_malformed_json_is_rejected():
    assert validate_message("{") == {"ok": False, "error": "ValidationError"}


def test_negative_sequence_is_rejected():
    assert validate_message(_frame("heartbeat", -1, {})) == {"ok": False, "error": "ValidationError"}


def test_oversize_frame_is_rejected():
    raw = _frame("auth", 0, {"token": "x" * 5000})
    assert len(raw.encode("utf-8")) > 4096
    assert validate_message(raw) == {"ok": False, "error": "MessageTooLarge"}


def test_sequence_must_increase():
    frames = [
        _frame("auth", 0, VALID_PAYLOADS["auth"]),
        _frame("heartbeat", 2, {}),
        _frame("player.input", 3, VALID_PAYLOADS["player.input"]),
        _frame("player.action", 4, VALID_PAYLOADS["player.action"]),
        _frame("lobby.join", 5, {}),
        _frame("lobby.leave", 6, {}),
        _frame("match.forfeit", 7, {}),
    ]
    assert [item["ok"] for item in validate_stream(frames)] == [True] * len(frames)

    repeated = validate_stream(
        [
            _frame("auth", 1, VALID_PAYLOADS["auth"]),
            _frame("heartbeat", 1, {}),
        ]
    )
    assert repeated[0]["ok"] is True
    assert repeated[1]["ok"] is False
    assert repeated[1]["error"] == "SequenceError"

    decreased = validate_stream(
        [
            _frame("auth", 4, VALID_PAYLOADS["auth"]),
            _frame("lobby.leave", 3, {}),
        ]
    )
    assert decreased[1]["ok"] is False
    assert decreased[1]["error"] == "SequenceError"


def test_invalid_input_still_consumes_its_sequence():
    results = validate_stream(
        [
            _frame("auth", 1, VALID_PAYLOADS["auth"]),
            _frame("player.input", 2, INVALID_PAYLOADS["player.input"]),
            _frame("heartbeat", 2, {}),
            _frame("heartbeat", 3, {}),
        ]
    )
    assert results[0]["ok"] is True
    assert results[1] == {"ok": False, "error": "ValidationError"}
    assert results[2]["error"] == "SequenceError"
    assert results[3]["ok"] is True


def test_token_stays_in_the_auth_payload_not_the_url():
    raw = _frame("auth", 0, VALID_PAYLOADS["auth"])
    accepted = validate_auth_transport(WEBSOCKET_PATH, raw)
    assert accepted["ok"] is True
    assert accepted["type"] == "auth"
    assert TOKEN not in WEBSOCKET_PATH

    in_query = validate_auth_transport(f"{WEBSOCKET_PATH}?token={TOKEN}", raw)
    assert in_query == {"ok": False, "error": "TokenInUrl"}

    renamed_query = validate_auth_transport(f"{WEBSOCKET_PATH}?session={TOKEN}", raw)
    assert renamed_query == {"ok": False, "error": "TokenInUrl"}


def test_first_socket_message_must_be_auth():
    heartbeat = _frame("heartbeat", 1, {})
    result = validate_auth_transport(WEBSOCKET_PATH, heartbeat)
    assert result["ok"] is False
    assert result["error"] == "AuthenticationRequired"
    assert result["type"] == "heartbeat"


@pytest.mark.parametrize("url", ["/api/v1/ws/extra", "/api/v1/game", "/socket"])
def test_auth_requires_the_websocket_path(url: str):
    raw = _frame("auth", 0, VALID_PAYLOADS["auth"])
    assert validate_auth_transport(url, raw) == {"ok": False, "error": "UnexpectedPath"}

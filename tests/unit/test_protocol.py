"""Client message checks."""

import pytest
from pydantic import ValidationError

from app.networking.protocol import parse_action, parse_input, parse_message
from app.networking.validation import RateLimiter, SequenceTracker


def test_message_requires_version_one():
    with pytest.raises(ValidationError):
        parse_message('{"version": 2, "type": "heartbeat", "sequence": 1, "payload": {}}')


def test_input_rejects_values_outside_the_unit_range():
    with pytest.raises(ValidationError):
        parse_input({"move_x": 2, "move_y": 0})


def test_sequence_must_increase():
    tracker = SequenceTracker()
    assert tracker.accept(1)
    assert not tracker.accept(1)


def test_lobby_message_parses():
    message = parse_message('{"version":1,"type":"lobby.join","sequence":2,"payload":{}}')
    assert message.type == "lobby.join"


def test_action_rejects_an_unknown_name():
    with pytest.raises(ValidationError):
        parse_action({"action": "fly"})


def test_rate_limiter_blocks_the_burst():
    limiter = RateLimiter(limit=2, window=10)
    assert limiter.allow()
    assert limiter.allow()
    assert not limiter.allow()

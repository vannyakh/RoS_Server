import json
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from tools.player_simulator import login, profile, register
from tools.protocol_validator import validate_message


async def test_register_login_and_profile_use_the_player_simulator(client):
    created = await register(client, "compat_user", "CompatPassword123!")
    assert created.status_code == 201
    signed_in = await login(client, "compat_user", "CompatPassword123!")
    assert signed_in.status_code == 200
    body = signed_in.json()
    assert set(body) == {"access_token", "expires_in", "token_type"}
    me = await profile(client, body["access_token"])
    assert me.status_code == 200
    assert me.json()["username"] == "compat_user"


def test_expired_token_is_rejected():
    token = jwt.encode(
        {"sub": "account", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    try:
        decode_access_token(token)
    except AppError as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("expired token was accepted")


def test_malformed_message_is_rejected():
    result = validate_message("{")
    assert result["ok"] is False
    assert result["error"] == "ValidationError"
    raw = json.dumps({"version": 1, "type": "nope", "sequence": 1, "payload": {}})
    assert validate_message(raw)["ok"] is False

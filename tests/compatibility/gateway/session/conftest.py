"""Lobby START -> match gateway tests (offline GateUDP._athlete_request)."""

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

ADDR = ("192.168.1.10", 20001)
BF_KEY = b"\xaa\xbb\xcc\xdd"

GATEWAY_MODULES = (
    "ros_server",
    "account_link",
    "athlete_requests",
    "battle.session",
    "battle",
    "battle_flow",
)


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    saved = {name: sys.modules.pop(name, None) for name in GATEWAY_MODULES}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture(autouse=True)
def gateway_loop():
    """Give each test its own current event loop.

    ros_server schedules with ``asyncio.get_event_loop().call_later``. Async
    tests that run earlier (pytest-asyncio / anyio) close or unset the
    policy's loop, so without this the gateway sees no current loop and a
    patch on one loop object misses the one the gateway uses.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@pytest.fixture
def reqs():
    return importlib.import_module("athlete_requests")


@pytest.fixture
def gw(monkeypatch, tmp_path):
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("GAME_DATE", "2022-04-20 12:00:00")
    monkeypatch.setenv("HALL_THEME_ID", "270000")
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = {"outfit": {}, "items": []}
    module.account_link._login_uid = "9000000123"
    module.account_link._current = {"gid": 9000000123, "nickname": "HallTest", "is_new": False}
    return module


@pytest.fixture
def recorder(gw, monkeypatch):
    calls = []
    real = gw.athlete_method

    def record(name, args, quiet=False):
        calls.append((name, args))
        return real(name, args, quiet=True)

    monkeypatch.setattr(gw, "athlete_method", record)
    return calls


@pytest.fixture
def udp(gw):
    u = gw.GateUDP(25000)
    u._last_bf[ADDR] = BF_KEY
    u._athlete_sent[ADDR] = True
    return u
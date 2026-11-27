"""Training / Special Distinction gateway tests — offline harness like supply and top-up."""

import importlib
import sys
from pathlib import Path

import pytest

_SUPPLY = Path(__file__).resolve().parents[1] / "supply"
if str(_SUPPLY) not in sys.path:
    sys.path.insert(0, str(_SUPPLY))

from supply_helpers import ADDR  # noqa: F401

GATEWAY_MODULES = (
    "ros_server",
    "account_link",
    "athlete_requests",
    "supply_cache",
    "training_event",
)


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    saved = {name: sys.modules.pop(name, None) for name in GATEWAY_MODULES}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def gw(monkeypatch, tmp_path):
    for var in (
        "LOBBY_SWITCHES_OFF",
        "ATHLETE_FREE_YUANBAO",
        "ATHLETE_PAY_YUANBAO",
        "HALL_THEME_ID",
        "SUPPLY_CATALOG_AT_LOGIN",
        "GATEWAY_FREE_BRAVE_BOOK_PASS",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("GATEWAY_FREE_BRAVE_BOOK_PASS", "on")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = {"yuanbao": 1000, "items": [], "outfit": {}}
    module.account_link._current = None

    def no_network(*args, **kwargs):
        raise AssertionError("training tests must not call RoS_Server")

    monkeypatch.setattr(module.account_link, "_call", no_network)
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
    return gw.GateUDP(25000)
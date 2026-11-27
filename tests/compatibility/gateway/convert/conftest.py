"""Convert repeats (iItemConvert) gateway tests."""

import importlib
import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

GATEWAY_MODULES = ("ros_server", "account_link", "athlete_requests", "supply_cache")

ADDR = ("10.0.0.4", 5000)


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
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000,4:0,9:0")
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    # prop 120920 appears in hall_catalog samples (quality from original_lobby)
    module.LOGIN_STATE = {
        "yuanbao": 1000,
        "items": [{"prop_id": 120920, "number": 3}, {"prop_id": 102004, "number": 1}],
        "outfit": {},
    }
    module.account_link._current = None
    monkeypatch.setattr(module.account_link, "_call", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("convert tests must not call RoS_Server")))
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
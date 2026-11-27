"""Supply (supplement box) gateway tests: import the gateway modules from bigworld_gateway/server,
as the gateway process does. No sockets are opened (GateUDP is built but never bound), no
RoS_Server call is made (account_link._call is replaced), and saved_accounts.json is redirected
to a temporary file."""

import importlib
import sys

import pytest

from supply_helpers import ADDR  # noqa: F401  (also puts bigworld_gateway/server on sys.path)


GATEWAY_MODULES = ("ros_server", "account_link", "athlete_requests", "supply_cache")


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    """Each test imports fresh gateway modules; the module objects other test packages imported
    at collection time are put back afterwards, so these tests leave sys.modules as they found it."""
    saved = {name: sys.modules.pop(name, None) for name in GATEWAY_MODULES}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def reqs():
    return importlib.import_module("athlete_requests")


@pytest.fixture
def gw(monkeypatch, tmp_path):
    for var in ("LOBBY_SWITCHES_OFF", "ATHLETE_FREE_YUANBAO", "ATHLETE_PAY_YUANBAO", "HALL_THEME_ID",
                "SUPPLY_CATALOG_AT_LOGIN", "SUPPLY_PREACK_WEEKLY_PUSH", "SUPPLY_CLEAR_WEEKLY_FLAGS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = {"yuanbao": 1000, "items": [], "outfit": {}}
    module.account_link._current = None

    def no_network(*args, **kwargs):
        raise AssertionError("supply tests must not call RoS_Server")

    monkeypatch.setattr(module.account_link, "_call", no_network)
    return module


@pytest.fixture
def recorder(gw, monkeypatch):
    """Record every Athlete client method the gateway builds, as (name, args); the bytes are
    still built by the real athlete_method, so the wire encoding is exercised too."""
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

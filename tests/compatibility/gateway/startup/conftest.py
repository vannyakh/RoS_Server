"""Gateway startup (createBasePlayer / login bundle) tests: import the gateway modules from
bigworld_gateway/server, as the gateway process does. No sockets are opened, no RoS_Server
call is made, and saved_accounts.json is redirected to a temporary file."""

import importlib
import sys
from pathlib import Path

import pytest

GATEWAY_SERVER = Path(__file__).resolve().parents[4] / "bigworld_gateway" / "server"
if str(GATEWAY_SERVER) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVER))

# bwdefs is dropped too, so every test starts with an empty process-wide .def cache.
GATEWAY_MODULES = ("ros_server", "account_link", "athlete_requests", "supply_cache", "bwdefs")


def _gateway_module_names():
    """GATEWAY_MODULES plus every other loaded module from bigworld_gateway/server. A module left
    loaded (training_event, lobby_events, ...) would keep the previous test's athlete_requests, so
    a patch on the fresh athlete_requests (game_now) would not reach it."""
    names = set(GATEWAY_MODULES)
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and Path(path).resolve().is_relative_to(GATEWAY_SERVER):
            names.add(name)
    return names


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    saved = {name: sys.modules.pop(name, None) for name in _gateway_module_names()}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def gw(monkeypatch, tmp_path):
    for var in ("LOBBY_SWITCHES_OFF", "ATHLETE_FREE_YUANBAO", "ATHLETE_PAY_YUANBAO", "HALL_THEME_ID",
                "TEST_ACCOUNT_NAME", "FORCE_NEW_ACCOUNT", "UNLOCK_ALL", "ATHLETE_SEED_ITEMS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = None
    module.account_link._current = None

    def no_network(*args, **kwargs):
        raise AssertionError("startup tests must not call RoS_Server")

    monkeypatch.setattr(module.account_link, "_call", no_network)
    return module

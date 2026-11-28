"""In-game Store (mall) gateway tests: import the gateway modules from bigworld_gateway/server,
as the gateway process does. No sockets are opened (GateUDP is built but never bound), no
RoS_Server call is made (account_link._call is replaced), and saved_accounts.json is redirected
to a temporary file. Pattern copied from tests/compatibility/gateway/supply/conftest.py."""

import importlib
import sys

import pytest

from store_helpers import ADDR  # noqa: F401  (also puts bigworld_gateway/server on sys.path)


GATEWAY_MODULES = ("ros_server", "account_link", "athlete_requests", "supply_cache")


@pytest.fixture(autouse=True)
def fresh_gateway_modules():
    """Each test imports fresh gateway modules; the module objects other test packages imported
    are put back afterwards, so these tests leave sys.modules as they found it."""
    saved = {name: sys.modules.pop(name, None) for name in GATEWAY_MODULES}
    yield
    for name, module in saved.items():
        sys.modules.pop(name, None)
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def gw(monkeypatch, tmp_path):
    """Local mode (not linked): 1000 diamonds and 10000 coins at login."""
    for var in ("LOBBY_SWITCHES_OFF", "ATHLETE_FREE_YUANBAO", "ATHLETE_PAY_YUANBAO", "HALL_THEME_ID",
                "CBP_GID", "FORCE_NEW_ACCOUNT", "TEST_ACCOUNT_NAME", "UNLOCK_ALL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = {"yuanbao": 1000, "items": [], "outfit": {}}
    module.account_link._current = None
    module.account_link._login_uid = None

    def no_network(*args, **kwargs):
        raise AssertionError("store tests must not call RoS_Server")

    monkeypatch.setattr(module.account_link, "_call", no_network)
    # No operator listings unless a test sets some (the real source would call RoS_Server).
    module.athlete_requests.set_listing_source(lambda: [])
    return module


@pytest.fixture
def listings(gw):
    """Mutable operator listing rows served as RoS_Server /gateway/store/listings."""
    rows = []
    gw.athlete_requests.set_listing_source(lambda: rows)
    return rows


class FakeApi:
    """Stand-in for account_link._call in linked mode: records every call, answers the purchase
    POST with `purchase_result` and the workshop/compound POST (coin buys) with `compound_result`
    (a dict, a callable taking the body, {"_error": code} or None = unreachable)."""

    def __init__(self):
        self.calls = []
        self.purchase_result = None
        self.compound_result = None
        self.listings = []
        self.retry_stale = []   # account_link._call(..., retry_stale=) per call, same order as calls

    def __call__(self, method, path, body, retry_stale=False):
        self.calls.append((method, path, body))
        self.retry_stale.append(retry_stale)
        if path.endswith("/purchase"):
            result = self.purchase_result
            return result(body) if callable(result) else result
        if path.endswith("/workshop/compound"):
            result = self.compound_result
            return result(body) if callable(result) else result
        if path == "/api/v1/gateway/store/listings":
            return {"listings": self.listings}
        # Side calls (state / outfit for recent_got, ...) are recorded and answered as "down", so
        # these tests pin only the purchase contract.
        return None

    def purchases(self):
        return [(p, b) for m, p, b in self.calls if m == "POST" and p.endswith("/purchase")]

    def compounds(self):
        return [(p, b) for m, p, b in self.calls if m == "POST" and p.endswith("/workshop/compound")]


@pytest.fixture
def api(gw, monkeypatch):
    """Linked mode: account_link resolved to a RoS_Server account; _call is FakeApi."""
    fake = FakeApi()
    monkeypatch.setattr(gw.account_link, "_call", fake)
    gw.athlete_requests.set_listing_source(gw.account_link.store_listings)
    gw.account_link._current = {"external_uid": "9879120763", "gid": 1, "is_new": False}
    gw.LOGIN_STATE = {"yuanbao": 1000, "items": [], "outfit": {}, "currencies": {"1": 10000}}
    return fake


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

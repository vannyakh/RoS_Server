"""Gateway tests for the functions synced from RosGG-Server-v2 82fb509 / b967a5a: lobby mail, rank,
top-up, VIP, Event / sign-in / activities, match results, match room and battle world.

Modelled on tests/compatibility/gateway/supply/conftest.py: the gateway modules are imported fresh
from bigworld_gateway/server, no socket is bound (GateUDP is built, never started), RoS_Server is
never called (account_link._call raises), GATEWAY_API_KEY is empty, saved_accounts.json, the mail
definitions file and match_results.jsonl are redirected to tmp_path."""

import importlib
import json
import sys

import pytest

from lobby_new_helpers import ADDR  # noqa: F401  (also puts bigworld_gateway/server on sys.path)


GATEWAY_MODULES = (
    "ros_server", "account_link", "athlete_requests", "supply_cache", "local_store", "profile_screens",
    "lobby_mail", "lobby_rank", "lobby_topup", "lobby_vip", "lobby_events", "client_pickle", "pay_goods",
    "match_results", "match_room", "battle_world", "battle_flow", "battle", "battle.session",
    "battle.requests",
)

ENV_CLEAR = (
    "LOBBY_SWITCHES_OFF", "ATHLETE_FREE_YUANBAO", "ATHLETE_PAY_YUANBAO", "HALL_THEME_ID",
    "SUPPLY_CATALOG_AT_LOGIN", "SUPPLY_PREACK_WEEKLY_PUSH", "SUPPLY_CLEAR_WEEKLY_FLAGS",
    "VIP_SILVER_LEVEL", "VIP_GOLD_LEVEL", "VIP_CARD_DAYS", "TOPUP_GRANT", "GATEWAY_PRIVATE_TOPUP",
    "CBP_GID", "ROOM_MODE", "ROOM_GHOST", "ROOM_CE", "ROOM_STATE_RELAY", "WORLD_VEHICLES", "WORLD_AIRDROP",
    "VEHICLE_CONTROL", "AIRDROP_ITEM_FORMAT", "AIRDROP_ITEMS", "EXPOSED_SHIFT_FROM", "EXPOSED_SHIFT",
    "CHUTE_MODE", "BATTLE_MAP", "AVATAR_ID",
)

# Mail definitions used by the mail tests (same shape as bigworld_gateway/server/lobby_mail.json).
TEST_MAILS = [
    {"id": 1, "type": 0, "title": "Text only", "sender": "RoS Server", "content": "hello",
     "props": [], "deadline_days": 0},
    {"id": 2, "type": 1, "title": "Gift", "sender": "RoS Server", "content": "gift",
     "props": [[120901, 1], [250175, 2]], "deadline_days": 0},
    {"id": 3, "type": 1, "title": "Expiring", "sender": "RoS Server", "content": "soon",
     "props": [[203011, 1]], "deadline_days": 7},
]


def _pop_gateway_modules():
    names = set(GATEWAY_MODULES) | {k for k in sys.modules if k.startswith("battle.modules.")}
    return {name: sys.modules.pop(name, None) for name in names}


@pytest.fixture(autouse=True)
def fresh_gateway_modules(monkeypatch, tmp_path):
    """Fresh gateway modules per test; the module objects other test packages imported are put
    back afterwards. Environment defaults are pinned before the modules read them at import."""
    for var in ENV_CLEAR:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    monkeypatch.setenv("MAIL_RELOAD", "off")              # keep the redirected MAIL_FILE
    monkeypatch.setenv("GAME_DATE", "2022-04-20 12:00:00")
    monkeypatch.setenv("MATCH_RESULTS_FILE", str(tmp_path / "match_results.jsonl"))
    monkeypatch.setenv("ROOM_SPAWN_DELAY", "0")
    saved = _pop_gateway_modules()
    yield
    _pop_gateway_modules()
    for name, module in saved.items():
        if module is not None:
            sys.modules[name] = module


@pytest.fixture
def mail_file(tmp_path):
    path = tmp_path / "lobby_mail.json"
    path.write_text(json.dumps(TEST_MAILS), encoding="utf-8")
    return path


@pytest.fixture
def gw(monkeypatch, tmp_path, mail_file):
    module = importlib.import_module("ros_server")
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = {"yuanbao": 1000, "items": [], "outfit": {}}
    module.account_link._current = None
    module.account_link._login_uid = None
    monkeypatch.setattr(module.lobby_mail, "MAIL_FILE", str(mail_file))

    def no_network(*args, **kwargs):
        raise AssertionError("lobby_new tests must not call RoS_Server")

    monkeypatch.setattr(module.account_link, "_call", no_network)
    return module


@pytest.fixture
def recorder(gw, monkeypatch):
    """Every Athlete client method the gateway builds, as (name, args). The bytes are still built
    by the real athlete_method, so an unknown method name still fails the request."""
    class Calls(list):
        pass

    calls = Calls()
    real = gw.athlete_method

    def record(name, args, quiet=False):
        out = real(name, args, quiet=True)      # raises KeyError for a name not in Athlete.def
        calls.append((name, args))
        return out

    monkeypatch.setattr(gw, "athlete_method", record)
    calls.real = real
    return calls


@pytest.fixture
def udp(gw):
    return gw.GateUDP(25000)

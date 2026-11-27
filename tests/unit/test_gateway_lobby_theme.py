"""Store -> Lobby Theme: BUY with diamonds (buyMultipleMallGood), Use (equipAppearance) and the
saved theme sent back at the next login."""

import importlib
import json
import re
import struct
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.gateway import GatewayOutfit, GatewayPurchaseRequest

ADDR = ("10.0.0.2", 5000)
SCHOOL_CAMPUS_GOOD = 10002      # mall good of the "Schoolgirl" lobby theme, 280 diamonds
SCHOOL_CAMPUS_PROP = 270002     # its hall prop (appearance_slots.json kind "theme")


@pytest.fixture
def gw(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.delenv("HALL_THEME_ID", raising=False)
    module = importlib.reload(importlib.import_module("ros_server"))
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = None
    module.account_link._current = None
    yield module
    for name in ("ros_server", "account_link", "athlete_requests"):
        sys.modules.pop(name, None)


class FakeRosServer:
    """account_link._call stand-in that validates bodies like the FastAPI routes do."""

    def __init__(self, yuanbao):
        self.yuanbao = yuanbao
        self.calls = []
        self.outfit = None

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        try:
            if path.endswith("/purchase"):
                req = GatewayPurchaseRequest.model_validate(body)
                if req.price > self.yuanbao:
                    return {"_error": 409}
                self.yuanbao -= req.price
                return {"yuanbao": self.yuanbao, "added": req.props}
            if path.endswith("/outfit"):
                self.outfit = GatewayOutfit.model_validate(body).model_dump()
                return self.outfit
        except ValidationError:
            return {"_error": 422}
        return None


def _link(gw, server, uid="9879120763"):
    gw.account_link._current = {"external_uid": uid, "gid": 1}
    gw.account_link._call = server
    gw.LOGIN_STATE = {"yuanbao": server.yuanbao, "items": [], "outfit": {}}


def _arr(ids):
    return struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", i) for i in ids)


def _multi_buy_args(goods):
    log = b"HallThemeMallMultiple"
    return _arr(goods) + _arr([1] * len(goods)) + _arr([]) + bytes([len(log)]) + log


def _buy(gw, udp, goods):
    return udp._athlete_request(ADDR, "buyMultipleMallGood", _multi_buy_args(goods))


@pytest.mark.parametrize("reason", ["mall-multi:[10002]", "mall-multi:[10002, 10003]", "Draw:{a b}", "", "x" * 200])
def test_ledger_reasons_always_pass_the_server_pattern(gw, reason):
    sent = gw.account_link.ledger_reason(reason)
    assert re.fullmatch(r"[a-z0-9_.:-]+", sent)
    assert len(sent) <= 64
    GatewayPurchaseRequest(price=0, props=[], reason=sent)


def test_lobby_theme_buy_is_charged_on_ros_server_and_owned(gw):
    server = FakeRosServer(30235)
    _link(gw, server)
    udp = gw.GateUDP(25000)

    reply = _buy(gw, udp, [SCHOOL_CAMPUS_GOOD])

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOL_CAMPUS_PROP])) in reply
    assert gw.athlete_method("onYBUpdated", struct.pack("<qqi", 30235 - 280, 0, 0)) in reply
    assert b"onBuyMallGoodFailed" not in reply
    (method, path, body), = [c for c in server.calls if c[1].endswith("/purchase")]
    assert body["price"] == 280 and body["props"] == [SCHOOL_CAMPUS_PROP]
    assert body["reason"] == "mall-multi:10002"
    assert server.yuanbao == 30235 - 280
    assert SCHOOL_CAMPUS_PROP in udp._owned(ADDR)


def test_lobby_theme_buy_above_the_balance_is_refused(gw):
    server = FakeRosServer(100)
    _link(gw, server)
    udp = gw.GateUDP(25000)

    reply = _buy(gw, udp, [SCHOOL_CAMPUS_GOOD])

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOL_CAMPUS_PROP])) not in reply
    assert server.yuanbao == 100
    assert SCHOOL_CAMPUS_PROP not in udp._owned(ADDR)


def test_lobby_theme_buy_without_ros_server_is_kept_locally(gw):
    gw.account_link._current = None
    gw.LOGIN_STATE = {"yuanbao": 30235, "items": [], "outfit": {}}
    udp = gw.GateUDP(25000)

    reply = _buy(gw, udp, [SCHOOL_CAMPUS_GOOD])

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOL_CAMPUS_PROP])) in reply
    saved = gw.local_state()
    assert saved["yuanbao"] == 30235 - 280
    assert {"prop_id": SCHOOL_CAMPUS_PROP} in saved["items"]


def test_using_a_lobby_theme_sets_and_saves_the_hall_background(gw):
    server = FakeRosServer(30235)
    _link(gw, server)
    gw.LOGIN_STATE["outfit"] = {"body": [], "wear": [2007]}
    udp = gw.GateUDP(25000)

    reply = udp._athlete_request(ADDR, "equipAppearance", struct.pack("<i", SCHOOL_CAMPUS_PROP))

    assert gw.athlete_method("onUpdateDtsHallThemeID", struct.pack("<i", SCHOOL_CAMPUS_PROP)) in reply
    assert server.outfit["theme"] == SCHOOL_CAMPUS_PROP
    assert server.outfit["wear"] == [2007]
    assert json.loads(Path(gw.ACCOUNTS_FILE).read_text("utf-8"))
    assert gw.local_state()["outfit"]["theme"] == SCHOOL_CAMPUS_PROP


def test_next_login_sends_the_saved_theme_instead_of_the_default(gw):
    theme_call = lambda tid: gw.athlete_method("onUpdateDtsHallThemeID", struct.pack("<i", tid))
    udp = gw.GateUDP(25000)

    gw.LOGIN_STATE = {"yuanbao": 0, "items": [], "outfit": {"theme": SCHOOL_CAMPUS_PROP}}
    assert gw.hall_theme_id() == SCHOOL_CAMPUS_PROP
    assert theme_call(SCHOOL_CAMPUS_PROP) in udp._lobby_data_calls()

    gw.LOGIN_STATE = {"yuanbao": 0, "items": [], "outfit": {}}
    assert gw.hall_theme_id() == 270000            # const.DEFAULT_HALL_THEME_ID, never 0
    assert theme_call(270000) in udp._lobby_data_calls()

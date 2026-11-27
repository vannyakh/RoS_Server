"""GateUDP handling of Athlete.appearanceCultivateCompound: linked (account_link.workshop_compound),
RoS_Server refusal/down, local mode, and the in-flight guard."""

import importlib
import struct
import sys

import pytest

ADDR = ("10.0.0.2", 5000)
THUNDER, LV1, LV2 = 142091, 142091, 142092


@pytest.fixture
def gw(monkeypatch, tmp_path):
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    monkeypatch.setenv("ATHLETE_SEED_CURRENCY", "1:10000,2:1000")
    module = importlib.reload(importlib.import_module("ros_server"))
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = None
    module.account_link._current = None
    yield module
    for name in ("ros_server", "account_link", "athlete_requests"):
        sys.modules.pop(name, None)


def _req(udp, cid, rid, ctype=0):
    return udp._athlete_request(ADDR, "appearanceCultivateCompound", struct.pack("<iii", cid, rid, ctype))


def _failed(gw, key, cid, rid, ctype=0, cur=0, price=0):
    return gw.athlete_method("onAppearanceCultivateCompoundFailed",
                             gw._bw_blob(gw.athlete_requests.CULTIVATE_TIPS[key].encode())
                             + struct.pack("<iiiii", cid, rid, ctype, cur, price))


class FakeCompound:
    def __init__(self, result):
        self.result, self.calls = result, []

    def __call__(self, request_id, require, consume, consume_currency, add, reason):
        self.calls.append((request_id, require, consume, consume_currency, add, reason))
        return self.result


def _link(gw, monkeypatch, fake, gold=1500, lv1=2):
    gw.account_link._current = {"external_uid": "9879120763", "gid": 1}
    monkeypatch.setattr(gw.account_link, "workshop_compound", fake, raising=False)
    gw.LOGIN_STATE = {"yuanbao": 0, "items": [{"prop_id": LV1, "number": lv1}],
                      "currencies": {"1": gold}, "outfit": {}}


def test_linked_success_sends_package_currency_and_result(gw, monkeypatch):
    fake = FakeCompound({"items": [{"prop_id": LV1, "number": 1}, {"prop_id": LV2, "number": 1}],
                         "currencies": {"1": 500}, "replayed": False})
    _link(gw, monkeypatch, fake)
    udp = gw.GateUDP(25000)

    reply = _req(udp, THUNDER, LV2)

    (request_id, require, consume, currency, add, reason), = fake.calls
    assert len(request_id) == 32
    assert (LV1, 2) in require and consume == [(LV1, 1)] and currency == [(1, 1000)] and add == [(LV2, 1)]
    assert reason == f"workshop:{THUNDER}:{LV2}"
    assert gw.athlete_method("onDelDtsAppearanceFoldedItem", struct.pack("<ii", LV1, 1)) in reply
    assert gw.athlete_method("onCurrencyUpdated", struct.pack("<iqi", 1, 500, 0)) in reply
    assert reply.endswith(gw.athlete_method("onAppearanceCultivateCompound", struct.pack("<i", LV2)))
    assert udp._counts(ADDR) == {LV1: 1, LV2: 1}
    assert udp._session_wallet(ADDR).balances[1] == 500
    # a second upgrade of the same rule is refused locally (already completed)
    assert _req(udp, THUNDER, LV2) == _failed(gw, "completed", THUNDER, LV2)
    assert len(fake.calls) == 1


def test_linked_refusal_sends_failed_and_changes_nothing(gw, monkeypatch):
    fake = FakeCompound({"_error": 409})
    _link(gw, monkeypatch, fake)
    udp = gw.GateUDP(25000)
    assert _req(udp, THUNDER, LV2) == _failed(gw, "props", THUNDER, LV2)
    assert udp._counts(ADDR) == {LV1: 2}
    assert udp._session_wallet(ADDR).balances[1] == 1500


def test_linked_server_down_sends_failed_and_changes_nothing(gw, monkeypatch):
    fake = FakeCompound(None)
    _link(gw, monkeypatch, fake)
    udp = gw.GateUDP(25000)
    assert _req(udp, THUNDER, LV2) == _failed(gw, "server", THUNDER, LV2)
    assert udp._counts(ADDR) == {LV1: 2}


def test_linked_without_account_link_function_fails_safely(gw, monkeypatch):
    _link(gw, monkeypatch, None)
    monkeypatch.delattr(gw.account_link, "workshop_compound", raising=False)
    udp = gw.GateUDP(25000)
    assert _req(udp, THUNDER, LV2) == _failed(gw, "server", THUNDER, LV2)


def test_not_enough_coins_reports_currency_and_price(gw, monkeypatch):
    fake = FakeCompound(None)
    _link(gw, monkeypatch, fake, gold=999)
    udp = gw.GateUDP(25000)
    assert _req(udp, THUNDER, LV2) == _failed(gw, "currency", THUNDER, LV2, cur=1, price=1000)
    assert fake.calls == []


def test_in_flight_guard_refuses_a_second_request(gw, monkeypatch):
    fake = FakeCompound(None)
    _link(gw, monkeypatch, fake)
    udp = gw.GateUDP(25000)
    udp._cultivate_busy.add(ADDR)
    assert _req(udp, THUNDER, LV2) == _failed(gw, "busy", THUNDER, LV2)
    assert fake.calls == []


def test_local_mode_applies_to_session_and_saves_target(gw):
    gw.LOGIN_STATE = {"yuanbao": 0, "items": [{"prop_id": LV1, "number": 2}], "outfit": {}}
    udp = gw.GateUDP(25000)
    reply = _req(udp, THUNDER, LV2)
    assert reply.endswith(gw.athlete_method("onAppearanceCultivateCompound", struct.pack("<i", LV2)))
    assert udp._counts(ADDR) == {LV1: 1, LV2: 1}
    assert udp._session_wallet(ADDR).balances[1] == 10000 - 1000    # ATHLETE_SEED_CURRENCY coins
    assert LV2 in [i["prop_id"] for i in gw.local_state()["items"]]


def test_login_currency_list_uses_ros_server_coins(gw):
    gw.LOGIN_STATE = {"currencies": {"1": 4321}}
    assert gw.login_gold() == 4321
    gw.LOGIN_STATE = {}
    assert gw.login_gold() == 10000


def test_login_stream_carries_counts_and_coins(gw, monkeypatch):
    state = {"yuanbao": 0, "items": [{"prop_id": LV1, "number": 2}, {"prop_id": LV2, "number": 0}],
             "currencies": {"1": 777}, "outfit": {}}
    monkeypatch.setattr(gw.account_link, "current", lambda: {"is_new": False, "nickname": "t", "gid": 1})
    monkeypatch.setattr(gw.account_link, "get_state", lambda: dict(state))
    msg = gw.athlete_create_message()
    assert struct.pack("<ii", LV1, 2) in msg                    # ITEM_DATA3 itemID, number
    assert struct.pack("<ii", LV2, 0) not in msg
    assert struct.pack("<iq", 1, 777) in msg

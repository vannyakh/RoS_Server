"""Gateway store honours the operator lobby-theme listings from RoS_Server
(/api/v1/gateway/store/listings): override price charged, off-sale theme hidden and refused,
client prices when RoS_Server is down."""

import importlib
import pickle
import struct
import sys
from pathlib import Path

import pytest

ADDR = ("10.0.0.2", 5000)
SCHOOLGIRL_GOOD, SCHOOLGIRL = 10002, 270002      # 280 diamonds in the client table
WEDDING_GOOD, WEDDING = 10004, 270004            # 280 diamonds in the client table


@pytest.fixture
def gw(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    monkeypatch.setenv("GATEWAY_API_KEY", "")
    module = importlib.reload(importlib.import_module("ros_server"))
    module.ACCOUNTS_FILE = str(tmp_path / "saved_accounts.json")
    module._SESSIONS.clear()
    module._ACTIVE = None
    module.LOGIN_STATE = None
    module.account_link._current = None
    module.account_link._listings_cache = (None, [])
    yield module
    for name in ("ros_server", "account_link", "athlete_requests"):
        sys.modules.pop(name, None)


class FakeRosServer:
    def __init__(self, yuanbao, listings=None, down=False):
        self.yuanbao, self.listings, self.down = yuanbao, listings or [], down
        self.calls = []

    def __call__(self, method, path, body, retry_stale=False):
        self.calls.append((method, path, body))
        if path == "/api/v1/gateway/store/listings":
            return None if self.down else {"listings": self.listings}
        if path.endswith("/purchase"):
            if body["price"] > self.yuanbao:
                return {"_error": 409}
            self.yuanbao -= body["price"]
            return {"yuanbao": self.yuanbao, "added": body["props"]}
        return None


def _link(gw, server):
    gw.account_link._current = {"external_uid": "9879120763", "gid": 1}
    gw.account_link._call = server
    gw.LOGIN_STATE = {"yuanbao": server.yuanbao, "items": [], "outfit": {}}


def _arr(ids):
    return struct.pack("<I", len(ids)) + b"".join(struct.pack("<i", i) for i in ids)


def _multi_buy(udp, goods):
    log = b"HallThemeMallMultiple"
    return udp._athlete_request(ADDR, "buyMultipleMallGood", _arr(goods) + _arr([1] * len(goods)) + _arr([]) + bytes([len(log)]) + log)


def _listing(item, good, on_sale=True, currency="diamond", price=0):
    return {"item_id": item, "goods_id": good, "on_sale": on_sale, "currency": currency, "price": price}


def _goods_in_reply(reply):
    """mallGoodID dict pickled inside an onQueryAvailableMallGoods reply."""
    start = reply.index(b"\x80\x02")
    return pickle.loads(reply[start:])


def test_override_price_is_listed_and_charged(gw):
    server = FakeRosServer(1000, [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, price=50)])
    _link(gw, server)
    udp = gw.GateUDP(25000)

    listed = gw.athlete_requests.mall_goods(0)[SCHOOLGIRL_GOOD]
    assert (listed["CURRENCY_ID"], listed["PRICE"], listed["DISCOUNT"]) == (2, 50, 100)
    assert gw.athlete_requests.mall_goods(0)[WEDDING_GOOD]["PRICE"] == 280          # untouched
    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) == (2, 50)
    assert gw.athlete_requests.hallprop_price(SCHOOLGIRL) == (2, 50)

    reply = _multi_buy(udp, [SCHOOLGIRL_GOOD, WEDDING_GOOD])

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOLGIRL, WEDDING])) in reply
    (_, _, body), = [c for c in server.calls if c[1].endswith("/purchase")]
    assert body["price"] == 50 + 280
    assert server.yuanbao == 1000 - 330


def test_single_buy_charges_the_override_price(gw):
    server = FakeRosServer(1000, [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, price=75)])
    _link(gw, server)
    udp = gw.GateUDP(25000)

    reply = udp._athlete_request(ADDR, "buyMallGood", struct.pack("<ii", SCHOOLGIRL_GOOD, 1))

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOLGIRL])) in reply
    assert server.yuanbao == 1000 - 75


def test_off_sale_theme_is_not_listed_and_refused(gw):
    server = FakeRosServer(1000, [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, on_sale=False, price=280)])
    _link(gw, server)
    udp = gw.GateUDP(25000)

    assert SCHOOLGIRL_GOOD not in gw.athlete_requests.mall_goods(0)
    assert WEDDING_GOOD in gw.athlete_requests.mall_goods(0)
    assert SCHOOLGIRL_GOOD not in _goods_in_reply(udp._athlete_request(ADDR, "queryAvailableMallGoods", b""))
    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) is None

    multi = _multi_buy(udp, [SCHOOLGIRL_GOOD])
    single = udp._athlete_request(ADDR, "buyMallGood", struct.pack("<ii", SCHOOLGIRL_GOOD, 1))
    hall = udp._athlete_request(ADDR, "buyDtsHallProp", struct.pack("<i", SCHOOLGIRL))

    def failed(good, cur):
        return gw.athlete_method("onBuyMallGoodFailed", gw._bw_blob(b"") + struct.pack("<iiii", good, 1, cur, 0)
                                 + struct.pack("<I", 0) + gw._bw_blob(b""))

    assert multi == failed(SCHOOLGIRL_GOOD, 2)
    assert single == failed(SCHOOLGIRL_GOOD, 0)
    assert hall == failed(SCHOOLGIRL, 0)
    assert not [c for c in server.calls if c[1].endswith("/purchase")]
    assert server.yuanbao == 1000
    assert SCHOOLGIRL not in udp._owned(ADDR)


def test_coin_listing_uses_the_gp_currency_and_charges_no_diamonds(gw):
    """Linked coin (GP) buys go through RoS_Server's workshop/compound (the gold path). This
    FakeRosServer answers it None (unreachable): refused, nothing granted, no diamonds charged."""
    server = FakeRosServer(1000, [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, currency="coin", price=900)])
    _link(gw, server)
    udp = gw.GateUDP(25000)

    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) == (gw.athlete_requests.GP, 900)
    reply = _multi_buy(udp, [SCHOOLGIRL_GOOD])

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOLGIRL])) not in reply
    assert reply == gw.athlete_method("onBuyMallGoodFailed", gw._bw_blob(b"") + struct.pack(
        "<iiii", SCHOOLGIRL_GOOD, 1, gw.athlete_requests.YUANBAO, 0) + struct.pack("<I", 0) + gw._bw_blob(b""))
    assert [c for c in server.calls if c[1].endswith("/purchase")] == []
    assert len([c for c in server.calls if c[1].endswith("/workshop/compound")]) == 1
    assert server.yuanbao == 1000
    assert SCHOOLGIRL not in udp._owned(ADDR)


def test_coin_listing_linked_success_spends_gold_through_workshop_compound(gw):
    server = FakeRosServer(1000, [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, currency="coin", price=900)])
    gold = [10000]

    def call(method, path, body, retry_stale=False):
        if path.endswith("/workshop/compound"):
            server.calls.append((method, path, body))
            gold[0] -= body["consume_currency"][0]["amount"]
            return {"items": [dict(a) for a in body["add"]], "currencies": {"1": gold[0]}, "replayed": False}
        return server(method, path, body)

    _link(gw, server)
    gw.account_link._call = call
    udp = gw.GateUDP(25000)

    reply = _multi_buy(udp, [SCHOOLGIRL_GOOD])

    assert gw.athlete_method("onBuyMallGood", _arr([SCHOOLGIRL])) in reply
    (_, path, body), = [c for c in server.calls if c[1].endswith("/workshop/compound")]
    assert path == "/api/v1/gateway/accounts/9879120763/workshop/compound"
    request_id = body.pop("request_id")
    assert 8 <= len(request_id) <= 64
    assert body == {"require": [], "consume": [],
                    "consume_currency": [{"currency_id": gw.athlete_requests.GP, "amount": 900}],
                    "add": [{"prop_id": SCHOOLGIRL, "number": 1}],
                    "reason": "mall-multi:10002"}
    assert gold[0] == 10000 - 900
    assert udp._session_wallet(ADDR).balances[gw.athlete_requests.GP] == 9100
    assert server.yuanbao == 1000
    assert [c for c in server.calls if c[1].endswith("/purchase")] == []
    assert SCHOOLGIRL in udp._owned(ADDR)


def test_ros_server_down_falls_back_to_client_prices(gw):
    server = FakeRosServer(1000, down=True)
    _link(gw, server)

    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) == (2, 280)
    assert SCHOOLGIRL_GOOD in gw.athlete_requests.mall_goods(0)


def test_listings_are_cached_then_refetched(gw, monkeypatch):
    server = FakeRosServer(1000, [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, price=10)])
    _link(gw, server)
    clock = [100.0]
    monkeypatch.setattr(gw.account_link.time, "monotonic", lambda: clock[0])

    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) == (2, 10)
    server.listings = [_listing(SCHOOLGIRL, SCHOOLGIRL_GOOD, price=20)]
    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) == (2, 10)        # cached
    clock[0] += gw.account_link.LISTINGS_TTL + 1
    assert gw.athlete_requests.mall_good_price(SCHOOLGIRL_GOOD) == (2, 20)        # no restart
    fetches = [c for c in server.calls if c[1] == "/api/v1/gateway/store/listings"]
    assert len(fetches) == 2

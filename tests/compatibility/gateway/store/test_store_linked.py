"""Store buys in linked mode: RoS_Server (account_link.purchase -> POST
/api/v1/gateway/accounts/{uid}/purchase) is the source of truth. account_link._call is FakeApi."""

import os
import re
import struct

import pytest

from store_helpers import (ADDR, BRIGADE, GOBI, GP, HAWK, TRAINING_GIFT, UNKNOWN, YUANBAO, added_items,
                           bought_props, buy, buy_multi, failed_args, names, yb_updates)

PURCHASE_PATH = "/api/v1/gateway/accounts/9879120763/purchase"
COMPOUND_PATH = "/api/v1/gateway/accounts/9879120763/workshop/compound"
# GatewayPurchaseRequest.request_id / GatewayCompoundRequest.request_id accept this.
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


def without_request_id(body):
    """(body without request_id, request_id); asserts the id has the accepted shape."""
    body = dict(body)
    request_id = body.pop("request_id")
    assert REQUEST_ID.fullmatch(request_id)
    return body, request_id


def prop(gw, good):
    return gw.athlete_requests.mall_good_prop(good)


def diamonds(udp):
    return udp._session_wallet(ADDR).balances[YUANBAO]


def ok(yuanbao, recent=None):
    def answer(body):
        return {"yuanbao": yuanbao, "added": body["props"], **({"recent_got": recent} if recent else {})}
    return answer


def test_linked_buy_posts_one_purchase_with_price_props_and_reason(gw, udp, recorder, api):
    api.purchase_result = ok(4321)
    buy(udp, BRIGADE, 2)
    p = prop(gw, BRIGADE)
    [(path, body)] = api.purchases()
    assert path == PURCHASE_PATH
    assert without_request_id(body)[0] == {"price": 418, "props": [p, p], "reason": "mall:10000001x2"}
    assert yb_updates(recorder) == [(4321, 0, 0)]               # RoS_Server balance, not the session math
    assert bought_props(recorder) == [p, p]
    assert added_items(recorder) == [p, p]
    assert diamonds(udp) == 4321
    assert p in udp._owned(ADDR) and udp._counts(ADDR)[p] == 2
    assert not os.path.exists(gw.ACCOUNTS_FILE)                 # nothing written locally when linked


def test_linked_multi_buy_reason_passes_the_ledger_pattern(gw, udp, recorder, api):
    api.purchase_result = ok(500)
    buy_multi(udp, [BRIGADE, GOBI], [1, 1])
    [(path, body)] = api.purchases()
    body, _request_id = without_request_id(body)
    assert body == {"price": 418, "props": [prop(gw, BRIGADE), prop(gw, GOBI)],
                    "reason": "mall-multi:10000001-10000002"}
    assert bought_props(recorder) == body["props"]


def test_linked_recent_got_from_ros_server_is_used(gw, udp, recorder, api):
    api.purchase_result = ok(700, recent=[7, 8])
    buy(udp, BRIGADE)
    assert udp._recent_got[ADDR][:2] == [prop(gw, BRIGADE), 7]


def test_linked_buy_over_local_balance_is_still_asked_to_ros_server(gw, udp, recorder, api):
    """The gateway does not pre-check the session wallet when linked; RoS_Server decides."""
    api.purchase_result = ok(20)
    buy(udp, HAWK)
    assert len(api.purchases()) == 1
    assert names(recorder)[-1] == "onBuyMallGood"


@pytest.mark.parametrize("code", [409, 422, 500])
def test_linked_refusal_fails_and_grants_nothing(gw, udp, recorder, api, code):
    api.purchase_result = {"_error": code}
    buy(udp, BRIGADE)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", BRIGADE, 1, YUANBAO, 209, [], b"")
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()
    assert not os.path.exists(gw.ACCOUNTS_FILE)


def test_linked_multi_refusal_fails_and_grants_nothing(gw, udp, recorder, api):
    api.purchase_result = {"_error": 409}
    buy_multi(udp, [BRIGADE, GOBI], [1, 1])
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert udp._owned(ADDR) == set()


def test_linked_unknown_good_never_reaches_ros_server(gw, udp, recorder, api):
    buy(udp, UNKNOWN)
    assert api.purchases() == []
    assert names(recorder) == ["onBuyMallGoodFailed"]


def test_linked_listings_come_from_ros_server_and_are_cached(gw, udp, recorder, api):
    api.listings = [{"goods_id": BRIGADE, "item_id": None, "on_sale": True, "currency": "diamond", "price": 5}]
    api.purchase_result = ok(995)
    buy(udp, BRIGADE)
    buy(udp, BRIGADE)
    assert [b["price"] for _p, b in api.purchases()] == [5, 5]
    listing_gets = [c for c in api.calls if c[1] == "/api/v1/gateway/store/listings"]
    assert len(listing_gets) == 1                                # LISTINGS_TTL cache


def test_linked_unreachable_refuses_the_buy(gw, udp, recorder, api):
    """Linked and RoS_Server unreachable (purchase -> None): the buy is refused. A local fallback
    would tell the client it succeeded while RoS_Server never records the charge or the item."""
    api.purchase_result = None
    buy(udp, BRIGADE)
    assert len(api.purchases()) == 1
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", BRIGADE, 1, YUANBAO, 209, [], b"")
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()
    assert not os.path.exists(gw.ACCOUNTS_FILE)


def test_linked_duplicate_buys_are_two_purchases_with_their_own_request_ids(gw, udp, recorder, api):
    """Two identical client buys are two purchases (the client sends no id): same body, each with
    its own request_id, so only an HTTP-level retry of one request is replayed by RoS_Server."""
    api.purchase_result = ok(600)
    buy(udp, BRIGADE)
    buy(udp, BRIGADE)
    (b1, id1), (b2, id2) = [without_request_id(b) for _p, b in api.purchases()]
    assert b1 == b2 and id1 != id2


def test_linked_purchase_carries_a_request_id(gw, udp, recorder, api):
    api.purchase_result = ok(600)
    buy(udp, BRIGADE)
    buy(udp, BRIGADE)
    ids = [b.get("request_id") for _p, b in api.purchases()]
    assert all(ids) and ids[0] != ids[1]


def test_linked_replayed_purchase_is_a_success(gw, udp, recorder, api):
    """RoS_Server answers a repeated request_id with the first result and replayed=true."""
    api.purchase_result = lambda body: {"yuanbao": 791, "added": body["props"], "replayed": True}
    buy(udp, BRIGADE)
    assert names(recorder)[-1] == "onBuyMallGood"
    assert diamonds(udp) == 791
    assert prop(gw, BRIGADE) in udp._owned(ADDR)


# ---- coin (GP) goods when linked: RoS_Server's workshop/compound is the only gold path -----------

def compound_ok(gold):
    def answer(body):
        return {"items": [{"prop_id": a["prop_id"], "number": a["number"]} for a in body["add"]],
                "currencies": {"1": gold}, "replayed": False}
    return answer


def test_linked_coin_good_spends_ros_server_gold_through_workshop_compound(gw, udp, recorder, api):
    api.compound_result = compound_ok(9900)
    buy(udp, TRAINING_GIFT, 2)
    p = prop(gw, TRAINING_GIFT)
    assert api.purchases() == []
    [(path, body)] = api.compounds()
    assert path == COMPOUND_PATH
    body, _request_id = without_request_id(body)
    assert body == {"require": [], "consume": [], "consume_currency": [{"currency_id": GP, "amount": 200}],
                    "add": [{"prop_id": p, "number": 2}], "reason": "mall:3003x2"}
    assert names(recorder)[0] == "onCurrencyUpdated" and names(recorder)[-1] == "onBuyMallGood"
    assert recorder[0][1] == struct.pack("<iqi", GP, 9900, 0)
    assert udp._session_wallet(ADDR).balances[GP] == 9900
    assert diamonds(udp) == 1000
    assert udp._counts(ADDR)[p] == 2
    assert not os.path.exists(gw.ACCOUNTS_FILE)


@pytest.mark.parametrize("answer", [None, {"_error": 409}])
def test_linked_coin_good_refused_or_unreachable_grants_nothing(gw, udp, recorder, api, answer):
    api.compound_result = answer
    buy(udp, TRAINING_GIFT)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", TRAINING_GIFT, 1, GP, 100, [], b"")
    assert udp._session_wallet(ADDR).balances[GP] == 10000
    assert udp._owned(ADDR) == set()


def test_linked_multi_buy_mixing_diamonds_and_coins_is_refused(gw, udp, recorder, api):
    """Two RoS_Server calls (purchase + compound) would not be one transaction, so a linked buy
    that needs both currencies is refused before anything is sent."""
    api.purchase_result = ok(600)
    api.compound_result = compound_ok(9900)
    buy_multi(udp, [TRAINING_GIFT, BRIGADE], [1, 1])
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert api.purchases() == [] and api.compounds() == []
    assert udp._owned(ADDR) == set()

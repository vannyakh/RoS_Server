"""Store buys in local mode (not linked to RoS_Server): buyMallGood, buyMallGoodInAppearanceMall,
buyMultipleMallGood and buyDtsHallProp. The session wallet holds 1000 diamonds and 10000 coins."""

import json
import struct

import pytest

from store_helpers import (ADDR, APPEARANCE, BRIGADE, GOBI, GP, HALL_PROP, HAWK, JAWS_3D, LIONHEART_X10,
                           NOT_A_HALL_PROP, SUIT, TRAINING_GIFT, UNKNOWN, YUANBAO, added_items,
                           bought_props, buy, buy_hall_prop, buy_multi, failed_args, names, yb_updates)


def prop(gw, good):
    return gw.athlete_requests.mall_good_prop(good)


def diamonds(udp, addr=ADDR):
    return udp._session_wallet(addr).balances[YUANBAO]


def saved(gw):
    path = gw.ACCOUNTS_FILE
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ---- buyMallGood ---------------------------------------------------------------------------------

@pytest.mark.parametrize("request_name", ["buyMallGood", "buyMallGoodInAppearanceMall"])
def test_buy_charges_the_table_price_and_grants_the_prop(gw, udp, recorder, request_name):
    reply = buy(udp, BRIGADE, name=request_name, coupons=[5, 6])   # coupons are ignored
    assert reply
    p = prop(gw, BRIGADE)
    assert names(recorder)[0] == "onYBUpdated"
    assert names(recorder)[-1] == "onBuyMallGood"
    assert "onUpdateRecentGotPropIDList" in names(recorder)
    assert yb_updates(recorder) == [(1000 - 209, 0, 0)]
    assert added_items(recorder) == [p]
    assert bought_props(recorder) == [p]
    assert diamonds(udp) == 791
    assert p in udp._owned(ADDR) and udp._counts(ADDR)[p] == 1


def test_price_comes_from_the_table_not_from_the_request(gw, udp, recorder):
    """The request carries only goodID, num, coupons and a log string; whatever the client
    puts in coupons / logStr, the charge is the table price."""
    buy(udp, BRIGADE, coupons=[0x7FFFFFFF])
    assert diamonds(udp) == 1000 - 209


def test_discounted_good_charges_the_discounted_price(gw, udp, recorder):
    buy(udp, LIONHEART_X10)
    assert diamonds(udp) == 1000 - 192
    assert bought_props(recorder) == [prop(gw, LIONHEART_X10)]


def test_buy_appearance_mall_good_sends_on_add_dts_appearance_item(gw, udp, recorder):
    udp._wallet[ADDR] = gw.athlete_requests.Wallet({YUANBAO: 20000, GP: 0})
    buy(udp, APPEARANCE, name="buyMallGoodInAppearanceMall")
    assert added_items(recorder) == [prop(gw, APPEARANCE)] == [499142]
    assert diamonds(udp) == 20000 - 9999


def test_buy_three_charges_three_and_grants_three(gw, udp, recorder):
    buy(udp, BRIGADE, 3)
    p = prop(gw, BRIGADE)
    assert diamonds(udp) == 1000 - 3 * 209
    assert bought_props(recorder) == [p, p, p]
    assert added_items(recorder) == [p, p, p]
    assert udp._counts(ADDR)[p] == 3


@pytest.mark.parametrize("num", [0, -4, 100, 0x7FFFFFFF])
def test_buy_with_num_outside_1_to_99_is_refused(gw, udp, recorder, num):
    """num is bounded to 1..MALL_MAX_NUM (99) before any prop list is built or anything charged."""
    buy(udp, BRIGADE, num)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", BRIGADE, num, 0, 0, [], b"")
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()
    assert saved(gw) == {}


def test_buy_99_is_the_largest_accepted_num(gw, udp, recorder):
    udp._wallet[ADDR] = gw.athlete_requests.Wallet({YUANBAO: 99 * 209, GP: 0})
    buy(udp, BRIGADE, 99)
    assert names(recorder)[-1] == "onBuyMallGood"
    assert len(bought_props(recorder)) == 99
    assert diamonds(udp) == 0


def test_not_enough_diamonds_fails_with_price_and_charges_nothing(gw, udp, recorder):
    reply = buy(udp, HAWK)
    assert reply and names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", HAWK, 1, YUANBAO, 1280, [], b"")
    assert diamonds(udp) == 1000
    assert prop(gw, HAWK) not in udp._owned(ADDR)
    assert saved(gw) == {}


def test_not_enough_for_num_fails_with_the_total(gw, udp, recorder):
    buy(udp, BRIGADE, 5)
    assert failed_args(recorder) == (b"", BRIGADE, 5, YUANBAO, 5 * 209, [], b"")
    assert diamonds(udp) == 1000


@pytest.mark.parametrize("good", [UNKNOWN, SUIT])
def test_unknown_or_suit_good_fails_with_zero_price(gw, udp, recorder, good):
    buy(udp, good, 2)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", good, 2, 0, 0, [], b"")
    assert diamonds(udp) == 1000
    assert saved(gw) == {}


def test_off_sale_good_cannot_be_bought(gw, udp, recorder, listings):
    listings.append({"goods_id": BRIGADE, "item_id": None, "on_sale": False, "currency": "diamond", "price": 1})
    buy(udp, BRIGADE)
    assert failed_args(recorder)[1:5] == (BRIGADE, 1, 0, 0)
    assert diamonds(udp) == 1000


def test_price_override_is_what_is_charged(gw, udp, recorder, listings):
    listings.append({"goods_id": BRIGADE, "item_id": None, "on_sale": True, "currency": "diamond", "price": 50})
    buy(udp, BRIGADE, 2)
    assert diamonds(udp) == 1000 - 100


def test_two_rapid_identical_buys_are_two_purchases(gw, udp, recorder):
    """The client sends no request id: two identical buyMallGood calls are two buys, each charged.
    (Transport-level retransmits are dropped before this handler by the reliable-seq code.)"""
    buy(udp, BRIGADE)
    buy(udp, BRIGADE)
    assert diamonds(udp) == 1000 - 2 * 209
    assert names(recorder).count("onBuyMallGood") == 2
    assert udp._counts(ADDR)[prop(gw, BRIGADE)] == 2


def test_coin_good_spends_coins(gw, udp, recorder):
    """A coin (GP) good is paid from the session wallet's GP balance (login_gold), not diamonds;
    the client gets iCurrency.onCurrencyUpdated(GP, new balance, 0) before the item."""
    buy(udp, TRAINING_GIFT)
    assert names(recorder)[0] == "onCurrencyUpdated" and names(recorder)[-1] == "onBuyMallGood"
    assert "onYBUpdated" not in names(recorder)
    assert recorder[0][1] == struct.pack("<iqi", GP, 10000 - 100, 0)
    assert udp._session_wallet(ADDR).balances[GP] == 10000 - 100
    assert diamonds(udp) == 1000
    assert bought_props(recorder) == [prop(gw, TRAINING_GIFT)]


def test_coin_good_without_enough_coins_is_refused(gw, udp, recorder):
    udp._wallet[ADDR] = gw.athlete_requests.Wallet({YUANBAO: 1000, GP: 99})
    before = dict(udp._session_wallet(ADDR).balances)
    buy(udp, TRAINING_GIFT)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", TRAINING_GIFT, 1, GP, 100, [], b"")
    after = udp._session_wallet(ADDR).balances
    assert after[YUANBAO] == 1000
    assert after[GP] == 99
    assert after == before
    assert udp._owned(ADDR) == set()


def test_good_in_a_currency_the_player_lacks_is_refused(gw, udp, recorder):
    """A good priced in a currency the gateway holds no balance for (208 here; 247 client goods
    use 208, others 22/209/218...) is refused, as buyMultipleMallGood refuses it."""
    buy(udp, JAWS_3D)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder)[1:5] == (JAWS_3D, 1, 208, 150)
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()


def test_reply_is_sent_even_if_the_extras_fail_after_settle(gw, udp, recorder, monkeypatch):
    """The player has been charged once _settle succeeds, so an error while building the item /
    recent-got updates still sends onBuyMallGood (and the charge stays)."""
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(udp, "_grant_props", broken)
    reply = buy(udp, BRIGADE)
    assert reply
    assert names(recorder)[-1] == "onBuyMallGood"
    assert bought_props(recorder) == [prop(gw, BRIGADE)]
    assert diamonds(udp) == 1000 - 209
    assert saved(gw)[f"inventory:{gw.account_link.current_gid()}"]["items"] == [prop(gw, BRIGADE)]


# ---- buyMultipleMallGood ---------------------------------------------------------------------------

def test_multi_buy_charges_the_total_once_and_grants_all(gw, udp, recorder):
    buy_multi(udp, [BRIGADE, GOBI], [1, 2])
    a, b = prop(gw, BRIGADE), prop(gw, GOBI)
    assert yb_updates(recorder) == [(1000 - 3 * 209, 0, 0)]
    assert bought_props(recorder) == [a, b, b]
    assert added_items(recorder) == [a, b, b]
    assert names(recorder)[-1] == "onBuyMallGood"
    assert diamonds(udp) == 1000 - 627


def test_multi_buy_pads_missing_nums_with_one(gw, udp, recorder):
    buy_multi(udp, [BRIGADE, GOBI], [])
    assert diamonds(udp) == 1000 - 418
    assert bought_props(recorder) == [prop(gw, BRIGADE), prop(gw, GOBI)]


@pytest.mark.parametrize("bad", [UNKNOWN, SUIT, JAWS_3D])
def test_multi_buy_with_one_bad_good_charges_and_grants_nothing(gw, udp, recorder, bad):
    buy_multi(udp, [BRIGADE, bad], [1, 1])
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", BRIGADE, 1, YUANBAO, 209, [], b"")
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()
    assert saved(gw) == {}


def test_multi_buy_over_balance_charges_nothing(gw, udp, recorder):
    buy_multi(udp, [BRIGADE, HAWK], [1, 1])
    assert failed_args(recorder) == (b"", BRIGADE, 1, YUANBAO, 209 + 1280, [], b"")
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()


def test_multi_buy_with_no_goods_fails(gw, udp, recorder):
    buy_multi(udp, [], [])
    assert failed_args(recorder) == (b"", 0, 1, YUANBAO, 0, [], b"")


def test_multi_buy_charges_coin_goods_in_coins(gw, udp, recorder):
    """Each good is charged in its own currency: diamonds and coins are totalled separately and
    settled once."""
    buy_multi(udp, [TRAINING_GIFT, BRIGADE], [1, 1])
    assert bought_props(recorder) == [prop(gw, TRAINING_GIFT), prop(gw, BRIGADE)]
    assert names(recorder)[:2] == ["onYBUpdated", "onCurrencyUpdated"]
    assert diamonds(udp) == 1000 - 209
    assert udp._session_wallet(ADDR).balances[GP] == 10000 - 100


def test_multi_buy_without_enough_coins_charges_nothing(gw, udp, recorder):
    udp._wallet[ADDR] = gw.athlete_requests.Wallet({YUANBAO: 1000, GP: 50})
    before = dict(udp._session_wallet(ADDR).balances)
    buy_multi(udp, [TRAINING_GIFT, BRIGADE], [1, 1])
    assert names(recorder) == ["onBuyMallGoodFailed"]
    after = udp._session_wallet(ADDR).balances
    assert after[YUANBAO] == 1000
    assert after[GP] == 50
    assert after == before
    assert udp._owned(ADDR) == set()


@pytest.mark.parametrize("bad_num", [0, -1, 100])
def test_multi_buy_with_a_num_outside_1_to_99_charges_and_grants_nothing(gw, udp, recorder, bad_num):
    buy_multi(udp, [BRIGADE, GOBI], [1, bad_num])
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert diamonds(udp) == 1000
    assert udp._owned(ADDR) == set()
    assert saved(gw) == {}


# ---- buyDtsHallProp ------------------------------------------------------------------------------

def test_hall_prop_buy_charges_its_listed_price(gw, udp, recorder):
    udp._wallet[ADDR] = gw.athlete_requests.Wallet({YUANBAO: 5000, GP: 0})
    buy_hall_prop(udp, HALL_PROP)
    assert names(recorder)[-1] == "onBuyMallGood"
    assert bought_props(recorder) == [HALL_PROP]
    assert added_items(recorder) == [HALL_PROP]
    assert diamonds(udp) == 5000 - 2280


def test_hall_prop_buy_without_enough_diamonds_fails(gw, udp, recorder):
    buy_hall_prop(udp, HALL_PROP)
    assert failed_args(recorder) == (b"", HALL_PROP, 1, YUANBAO, 2280, [], b"")
    assert diamonds(udp) == 1000


def test_hall_prop_taken_off_sale_fails(gw, udp, recorder, listings):
    listings.append({"goods_id": None, "item_id": HALL_PROP, "on_sale": False, "currency": "diamond", "price": 1})
    buy_hall_prop(udp, HALL_PROP)
    assert failed_args(recorder) == (b"", HALL_PROP, 1, 0, 0, [], b"")


def test_hall_prop_price_override_applies(gw, udp, recorder, listings):
    listings.append({"goods_id": None, "item_id": HALL_PROP, "on_sale": True, "currency": "diamond", "price": 10})
    buy_hall_prop(udp, HALL_PROP)
    assert diamonds(udp) == 1000 - 10


def test_hall_prop_without_a_price_is_refused(gw, udp, recorder):
    """A prop with no price (not in hallprop_prices.json, no listing) is not for sale."""
    buy_hall_prop(udp, NOT_A_HALL_PROP)
    assert names(recorder) == ["onBuyMallGoodFailed"]
    assert failed_args(recorder) == (b"", NOT_A_HALL_PROP, 1, 0, 0, [], b"")
    assert NOT_A_HALL_PROP not in udp._owned(ADDR)
    assert diamonds(udp) == 1000
